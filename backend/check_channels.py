import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import engine
from sqlmodel import Session, select
import models
import src.adapters.db.channel_models as channel_models
import src.adapters.db.crm_models as crm_models

with Session(engine) as session:
    channels = session.exec(select(channel_models.ChannelSession)).all()
    print(f"Found {len(channels)} channels.")
    for c in channels:
        print(f"ID: {c.id}, Type: {c.channel_type}, Status: {c.status}")
