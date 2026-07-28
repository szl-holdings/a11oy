"""Minimal load target mounting the production GDW router."""

from fastapi import FastAPI

from routers.gdw_frontier import register


app = FastAPI(
    title="GDW isolated benchmark target",
    docs_url=None,
    redoc_url=None,
)
register(app, ns="a11oy")
