from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/graph", tags=["graph"])


class NodeBase(BaseModel):
    id: str
    type: str
    name: str
    file_path: str
    line_start: int
    line_end: int
    metadata: dict = {}


class EdgeBase(BaseModel):
    id: str
    source: str
    target: str
    type: str
    metadata: dict = {}


class GraphResponse(BaseModel):
    nodes: list[NodeBase]
    edges: list[EdgeBase]
    total_nodes: int
    total_edges: int


class GraphQuery(BaseModel):
    node_type: Optional[str] = None
    edge_type: Optional[str] = None
    file_path: Optional[str] = None
    limit: int = 100
    offset: int = 0


@router.get("", response_model=GraphResponse)
async def get_graph(query: GraphQuery = Depends()) -> GraphResponse:
    return GraphResponse(nodes=[], edges=[], total_nodes=0, total_edges=0)


@router.post("/parse")
async def parse_codebase(path: str) -> dict:
    return {"status": "accepted", "path": path, "parsed_files": 0, "nodes": 0, "edges": 0}


@router.get("/export")
async def export_graph(format: str = "json") -> dict:
    return {"format": format, "data": "export placeholder"}