from .subcommands.run import run

import carrotlite as c
import click

@click.group(invoke_without_command=True)
@click.option("--version","-v",is_flag=True)
@click.pass_context
def carrotlite(ctx,version):
    if ctx.invoked_subcommand == None :
        if version:
            click.echo(c.__version__)
        else:
            click.echo(ctx.get_help()) 
        return

carrotlite.add_command(run, "run")

if __name__ == "__main__":
  carrotlite()
