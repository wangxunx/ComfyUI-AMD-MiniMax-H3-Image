"""Image generation and editing node for MiniMax H3 Image on the AMD gateway.

The gateway issues one API key per registered user, so the key must never become part of a
workflow: widget values are serialized into workflow JSON and embedded into output file metadata,
which would leak every user's key as soon as they share a workflow or a generated image. The key
is therefore read from a file in the ComfyUI user directory, leaving only the creative parameters
in the graph.
"""

import os

import folder_paths
from comfy_api.latest import IO
from comfy_api_nodes.apis.minimax import (
    Hailuo03ImageContent,
    Hailuo03ImageContentUrl,
    Hailuo03TaskCreationResponse,
    Hailuo03TaskQueryResponse,
    Hailuo03TextContent,
)
from comfy_api_nodes.nodes_minimax import _hailuo03_resolve_ref_tags
from comfy_api_nodes.util import (
    ApiEndpoint,
    download_url_to_image_tensor,
    poll_op,
    sync_op,
    tensor_to_base64_string,
    validate_string,
)
from pydantic import BaseModel

BASE_URL = "https://h3.oneclickamd.ai"
API_KEY_FILENAME = "h3_gateway_api_key.txt"
REGISTRATION_URL = "https://h3.oneclickamd.ai"
MODEL = "MiniMax-H3-Image"
ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"]
SIZES = ["1K", "2K"]
MAX_REFERENCE_IMAGES = 3
MAX_PROMPT_LENGTH = 8000
FAILED_STATUSES = ["failed", "cancelled"]


class TaskCreationRequest(BaseModel):
    model: str
    content: list[Hailuo03TextContent | Hailuo03ImageContent]
    aspect_ratio: str
    seed: int
    quality: str | None = None


def api_key_file() -> str:
    return os.path.join(folder_paths.get_user_directory(), API_KEY_FILENAME)


def resolve_api_key() -> str:
    key = ""
    if os.path.isfile(api_key_file()):
        with open(api_key_file(), encoding="utf-8") as f:
            key = f.read().strip()
    if not key:
        raise Exception(
            f"No API key configured. Register at {REGISTRATION_URL} to get one, then save the key to "
            f"{api_key_file()}."
        )
    return key


class AMDMiniMaxH3Image(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="AMDMiniMaxH3Image",
            display_name="AMD MiniMax H3 Image",
            category="image/MiniMax",
            description="Generate images from text, or edit and combine up to 3 reference images, with "
            "MiniMax H3-Image on the AMD gateway. Refer to the references in the prompt by their order: "
            "@Image1, @Image2, @Image3. "
            f"Requires an account: register at {REGISTRATION_URL}, then save your key to "
            f"{API_KEY_FILENAME} in the ComfyUI user directory.",
            inputs=[
                IO.String.Input(
                    "prompt",
                    multiline=True,
                    default="",
                    tooltip="Text prompt describing the image to generate, or the edit to apply to the "
                    "reference images. At most 8,000 characters.",
                ),
                IO.Combo.Input(
                    "aspect_ratio",
                    options=ASPECT_RATIOS,
                    default="1:1",
                    tooltip="Aspect ratio of the output image. Edits are reframed to it rather than keeping "
                    "the shape of the reference images.",
                ),
                IO.Int.Input(
                    "seed",
                    default=42,
                    min=0,
                    max=2**31 - 1,
                    control_after_generate=True,
                    tooltip="The same prompt, settings and seed give the same image. When editing an image "
                    "you generated, use a different seed from the one that made it: the same noise sharpens "
                    "the image on every pass.",
                ),
                IO.Autogrow.Input(
                    "images",
                    template=IO.Autogrow.TemplateNames(
                        IO.Image.Input("image"),
                        names=[f"image_{i}" for i in range(1, MAX_REFERENCE_IMAGES + 1)],
                        min=0,
                    ),
                    optional=True,
                    tooltip="Optional reference images to edit or combine, referred to in the prompt as "
                    f"@Image1..@Image{MAX_REFERENCE_IMAGES} in connection order. Up to {MAX_REFERENCE_IMAGES}.",
                ),
                # Last, so workflows saved before this input existed keep their widget values in place.
                IO.Combo.Input(
                    "size",
                    options=SIZES,
                    default="1K",
                    tooltip="1K is about 1MP (1024x1024 at 1:1) for 4 credits. 2K is about 4MP (2048x2048 at "
                    "1:1, 2688x1536 at 16:9) for 16 credits. Both apply to edits too.",
                ),
            ],
            outputs=[IO.Image.Output()],
            hidden=[IO.Hidden.unique_id],
        )

    @classmethod
    async def execute(
        cls, prompt: str, aspect_ratio: str, seed: int, size: str, images: dict = None
    ) -> IO.NodeOutput:
        # The gateway requires exactly one non-empty text item even when reference images are supplied.
        validate_string(prompt, strip_whitespace=True, min_length=1, max_length=MAX_PROMPT_LENGTH)
        # A slot can carry a batch, and every frame in it counts as its own reference image.
        frames = [frame for tensor in (images or {}).values() for frame in tensor]
        if len(frames) > MAX_REFERENCE_IMAGES:
            raise ValueError(
                f"MiniMax H3 Image accepts up to {MAX_REFERENCE_IMAGES} reference images, got {len(frames)}."
            )
        prompt = _hailuo03_resolve_ref_tags(prompt, {"image": len(frames)})
        headers = {"Authorization": f"Bearer {resolve_api_key()}"}
        # Images go through the video paths: the gateway is wire-compatible with the MiniMax API,
        # where "video" in the path is fixed. The model field decides what comes back. Steps and
        # guidance are pinned by the gateway, which refuses any explicit value, so they are left out.
        response = await sync_op(
            cls,
            ApiEndpoint(path=f"{BASE_URL}/v2/video_generation", method="POST", headers=headers),
            response_model=Hailuo03TaskCreationResponse,
            data=TaskCreationRequest(
                model=MODEL,
                # Reference images are what turns this into an edit. They are inlined as data URIs,
                # since the gateway has no upload endpoint to reference.
                content=[
                    Hailuo03TextContent(text=prompt),
                    *(
                        Hailuo03ImageContent(
                            image_url=Hailuo03ImageContentUrl(
                                url=f"data:image/png;base64,{tensor_to_base64_string(frame)}"
                            ),
                            role="reference",
                        )
                        for frame in frames
                    ),
                ],
                aspect_ratio=aspect_ratio,
                seed=seed,
                quality="hd" if size == "2K" else None,
            ),
        )
        task_result = await poll_op(
            cls,
            ApiEndpoint(path=f"{BASE_URL}/v2/query/video_generation/{response.task_id}", headers=headers),
            response_model=Hailuo03TaskQueryResponse,
            status_extractor=lambda r: r.task.status,
            failed_statuses=FAILED_STATUSES,
            poll_interval=2,
        )
        image_url = task_result.task.content.url if task_result.task.content else None
        if not image_url:
            raise Exception(f"No image URL in the response: {task_result.model_dump()}")
        return IO.NodeOutput(await download_url_to_image_tensor(image_url, cls=cls))
