from sqlalchemy import Column, String, Integer, Text, ForeignKey, Index, DateTime
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False, index=True)
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)
    node_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    outgoing_edges = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.source_id",
        back_populates="source",
        lazy="dynamic",
    )
    incoming_edges = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.target_id",
        back_populates="target",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_graph_nodes_type_name", "type", "name"),
        Index("ix_graph_nodes_file_type", "file_path", "type"),
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True)
    source_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    target_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    edge_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    source = relationship("GraphNode", foreign_keys=[source_id], back_populates="outgoing_edges")
    target = relationship("GraphNode", foreign_keys=[target_id], back_populates="incoming_edges")

    __table_args__ = (
        Index("ix_graph_edges_source_type", "source_id", "type"),
        Index("ix_graph_edges_target_type", "target_id", "type"),
        Index("ix_graph_edges_type", "type"),
    )


class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id = Column(String, primary_key=True)
    root_path = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, running, completed, failed
    total_files = Column(Integer, default=0)
    parsed_files = Column(Integer, default=0)
    total_nodes = Column(Integer, default=0)
    total_edges = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)