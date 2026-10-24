from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from uuid import uuid4

from app.core.config import settings
from app.core.database import get_session
from app.models.graph import GraphNode, GraphEdge, ParseJob
from app.services.ast_parser import parse_codebase

router = APIRouter(prefix="/graph", tags=["graph"])


class NodeBase(BaseModel):
    id: str
    type: str
    name: str
    file_path: str
    line_start: int
    line_end: int
    metadata: dict = {}

    class Config:
        from_attributes = True


class EdgeBase(BaseModel):
    id: str
    source: str
    target: str
    type: str
    metadata: dict = {}

    class Config:
        from_attributes = True


class GraphResponse(BaseModel):
    nodes: list[NodeBase]
    edges: list[EdgeBase]
    total_nodes: int
    total_edges: int


class GraphQuery(BaseModel):
    node_type: Optional[str] = None
    edge_type: Optional[str] = None
    file_path: Optional[str] = None
    name: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ParseRequest(BaseModel):
    path: str


class ParseResponse(BaseModel):
    job_id: str
    status: str
    path: str
    message: str


class ExportQuery(BaseModel):
    format: Literal["json", "graphml"] = "json"


def node_to_base(node: GraphNode) -> NodeBase:
    return NodeBase(
        id=node.id,
        type=node.type,
        name=node.name,
        file_path=node.file_path,
        line_start=node.line_start,
        line_end=node.line_end,
        metadata=node.node_metadata or {},
    )


def edge_to_base(edge: GraphEdge) -> EdgeBase:
    return EdgeBase(
        id=edge.id,
        source=edge.source_id,
        target=edge.target_id,
        type=edge.type,
        metadata=edge.edge_metadata or {},
    )


@router.get("", response_model=GraphResponse)
async def get_graph(
    node_type: Optional[str] = Query(None),
    edge_type: Optional[str] = Query(None),
    file_path: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> GraphResponse:
    """Query graph nodes and edges with filters and pagination."""
    # Build node query
    node_query = select(GraphNode)
    if node_type:
        node_query = node_query.where(GraphNode.type == node_type)
    if file_path:
        node_query = node_query.where(GraphNode.file_path.like(f"%{file_path}%"))
    if name:
        node_query = node_query.where(GraphNode.name.like(f"%{name}%"))

    # Get total count
    count_query = select(func.count()).select_from(node_query.subquery())
    total_nodes = (await session.execute(count_query)).scalar_one()

    # Get paginated nodes
    node_query = node_query.order_by(GraphNode.file_path, GraphNode.line_start).limit(limit).offset(offset)
    nodes_result = await session.execute(node_query)
    nodes = [node_to_base(n) for n in nodes_result.scalars().all()]

    # Get edges for these nodes
    node_ids = [n.id for n in nodes]
    edge_query = select(GraphEdge).where(
        or_(GraphEdge.source_id.in_(node_ids), GraphEdge.target_id.in_(node_ids))
    )
    if edge_type:
        edge_query = edge_query.where(GraphEdge.type == edge_type)

    edges_result = await session.execute(edge_query)
    edges = [edge_to_base(e) for e in edges_result.scalars().all()]

    # Total edges (for the filtered nodes)
    total_edges = len(edges)

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        total_nodes=total_nodes,
        total_edges=total_edges,
    )


@router.post("/parse", response_model=ParseResponse)
async def parse_codebase_endpoint(request: ParseRequest, session: AsyncSession = Depends(get_session)) -> ParseResponse:
    """Parse a codebase and store the graph."""
    job_id = str(uuid4())

    # Create job record
    job = ParseJob(
        id=job_id,
        root_path=request.path,
        status="running",
    )
    session.add(job)
    await session.flush()

    try:
        result = parse_codebase(request.path)

        # Store nodes
        for node in result.nodes:
            session.add(node)

        # Store edges
        for edge in result.edges:
            session.add(edge)

        # Update job
        job.status = "completed" if not result.errors else "completed_with_errors"
        job.total_files = len(set(n.file_path for n in result.nodes if n.type == "module"))
        job.parsed_files = job.total_files
        job.total_nodes = len(result.nodes)
        job.total_edges = len(result.edges)
        if result.errors:
            job.error_message = "; ".join(result.errors[:10])

        await session.commit()

        return ParseResponse(
            job_id=job_id,
            status=job.status,
            path=request.path,
            message=f"Parsed {job.total_files} files: {len(result.nodes)} nodes, {len(result.edges)} edges"
            + (f". Errors: {len(result.errors)}" if result.errors else ""),
        )

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Parse failed: {e}")


@router.get("/export")
async def export_graph(
    format: Literal["json", "graphml"] = Query("json"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Export the full graph as JSON or GraphML."""
    nodes_result = await session.execute(select(GraphNode))
    nodes = nodes_result.scalars().all()

    edges_result = await session.execute(select(GraphEdge))
    edges = edges_result.scalars().all()

    if format == "json":
        return {
            "format": "json",
            "nodes": [node_to_base(n).model_dump() for n in nodes],
            "edges": [edge_to_base(e).model_dump() for e in edges],
        }

    # GraphML format
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
        '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns',
        '         http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
        '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
        '  <key id="name" for="node" attr.name="name" attr.type="string"/>',
        '  <key id="file_path" for="node" attr.name="file_path" attr.type="string"/>',
        '  <key id="line_start" for="node" attr.name="line_start" attr.type="int"/>',
        '  <key id="line_end" for="node" attr.name="line_end" attr.type="int"/>',
        '  <key id="edge_type" for="edge" attr.name="type" attr.type="string"/>',
        '  <graph id="G" edgedefault="directed">',
    ]

    for node in nodes:
        lines.append(f'    <node id="{node.id}">')
        lines.append(f'      <data key="type">{node.type}</data>')
        lines.append(f'      <data key="name">{node.name}</data>')
        lines.append(f'      <data key="file_path">{node.file_path}</data>')
        lines.append(f'      <data key="line_start">{node.line_start}</data>')
        lines.append(f'      <data key="line_end">{node.line_end}</data>')
        lines.append("    </node>")

    for edge in edges:
        lines.append(f'    <edge id="{edge.id}" source="{edge.source_id}" target="{edge.target_id}">')
        lines.append(f'      <data key="edge_type">{edge.type}</data>')
        lines.append("    </edge>")

    lines.extend(["  </graph>", "</graphml>"])

    return {"format": "graphml", "data": "\n".join(lines)}