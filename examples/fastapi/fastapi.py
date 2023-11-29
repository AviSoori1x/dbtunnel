# Databricks notebook source
# MAGIC %pip install "git+https://github.com/stikkireddy/dbtunnel.git#egg=dbtunnel[fastapi]"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <html>
        <head>
            <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
            <h1>Hello, FastAPI!</h1>
            <button onclick="alert('Button Clicked!')">Click me</button>
        </body>
    </html>
    """

# COMMAND ----------

from dbtunnel import dbtunnel
dbtunnel.fastapi(app).run()

# COMMAND ----------


