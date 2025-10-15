import os


def graphviz_render(
        body: str,
        filename="temp.gv",
        relpath: str = None,
        engine: str = "dot",
        format: str = "png",
        *args,
        **kwargs,
) -> None:
    from graphviz import Source

    if relpath is not None:
        filename = os.path.join(
            os.path.split(relpath)[0],
            filename
        )

    try:

        s = Source(body, engine=engine, filename=filename, format=format, *args, **kwargs)
        s.view()
    finally:
        if os.path.exists(filename):
            os.unlink(filename)
