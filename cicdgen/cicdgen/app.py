from typer import Typer

from . import build, generate

app = Typer()

app.command("build")(build.command)
app.command("generate")(generate.command)
