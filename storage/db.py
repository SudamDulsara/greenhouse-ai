# storage/db.py
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Session, create_engine, select
from datetime import datetime
from config import settings
import json

class Scenario(SQLModel, table=True):
    __tablename__ = "scenario"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    location: str
    area: float
    season: str
    goal: str
    organic: bool
    result_json: str  # full plan JSON as string

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.db_url,
            echo=False,
            connect_args={"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
        )
    return _engine

def init_db():
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

def save_scenario(name: str, inputs: Dict[str, Any], results: Dict[str, Any]) -> int:
    engine = get_engine()
    with Session(engine) as ses:
        scen = Scenario(
            name=name,
            location=str(inputs["location"]),
            area=float(inputs["area"]),
            season=str(inputs["season"]),
            goal=str(inputs["goal"]),
            organic=bool(inputs["organic"]),
            result_json=json.dumps(results),
        )
        ses.add(scen)
        ses.commit()
        ses.refresh(scen)
        return scen.id

def list_scenarios(limit: int = 50) -> List[Scenario]:
    engine = get_engine()
    with Session(engine) as ses:
        rows = ses.exec(select(Scenario).order_by(Scenario.created_at.desc()).limit(limit)).all()
        return rows

def load_scenario(scenario_id: int) -> Dict[str, Any]:
    engine = get_engine()
    with Session(engine) as ses:
        scen = ses.get(Scenario, scenario_id)
        if not scen:
            raise ValueError("Scenario not found")
        return json.loads(scen.result_json)

def delete_scenario(scenario_id: int) -> None:
    engine = get_engine()
    with Session(engine) as ses:
        scen = ses.get(Scenario, scenario_id)
        if scen:
            ses.delete(scen)
            ses.commit()
