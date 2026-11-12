from typing_extensions import override

from comfy_api.latest import IO, ComfyExtension

from .nodes import AMDMiniMaxH3Image


class AMDMiniMaxH3ImageExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[IO.ComfyNode]]:
        return [AMDMiniMaxH3Image]


async def comfy_entrypoint() -> AMDMiniMaxH3ImageExtension:
    return AMDMiniMaxH3ImageExtension()
