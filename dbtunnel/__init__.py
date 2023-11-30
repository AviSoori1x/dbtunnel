from dbtunnel.bokeh import BokehTunnel
from dbtunnel.fastapi import FastApiAppTunnel
from dbtunnel.flask import FlaskAppTunnel
from dbtunnel.gradio import GradioAppTunnel
from dbtunnel.nicegui import NiceGuiAppTunnel
from dbtunnel.stable_diffusion_ui import StableDiffusionUITunnel
from dbtunnel.streamlit import StreamlitTunnel


class AppTunnels:

    @staticmethod
    def fastapi(app, port: int = 8080):
        return FastApiAppTunnel(app, port)

    @staticmethod
    def gradio(app, port: int = 8080):
        return GradioAppTunnel(app, port)

    @staticmethod
    def nicegui(app, storage_secret: str = "", port: int = 8080):
        return NiceGuiAppTunnel(app, storage_secret, port)

    @staticmethod
    def streamlit(path, port: int = 8080):
        return StreamlitTunnel(path, port)

    @staticmethod
    def stable_diffusion_ui(no_gpu: bool, port: int = 7860, enable_insecure_extensions: bool = False,
                            extra_flags: str = ""):
        # todo auto detect with torch
        return StableDiffusionUITunnel(no_gpu, port, enable_insecure_extensions, extra_flags)

    @staticmethod
    def bokeh(path, port: int = 8080):
        return BokehTunnel(path, port)

    @staticmethod
    def flask(app, port: int = 8080):
        return FlaskAppTunnel(app, port)


dbtunnel = AppTunnels()
