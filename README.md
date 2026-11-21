# ComfyUI-AMD-MiniMax-H3-Image

ComfyUI node for MiniMax H3 Image text-to-image and multi-image editing through the AMD gateway. It
follows ComfyUI's built-in `MiniMax H3 Image` partner node, limited to what the gateway serves.

## Install

Search for `ComfyUI-AMD-MiniMax-H3-Image` in ComfyUI Manager, or install it from the registry:

```bash
comfy node install amd-minimax-h3-image
```

To install from source instead:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/wangxunx/ComfyUI-AMD-MiniMax-H3-Image.git
```

Restart ComfyUI. No extra Python dependencies are required. ComfyUI 0.44.0 or newer is needed.

## Configure your API key

Register at https://h3.oneclickamd.ai/?utm_source=comfyui to get a key, then save it to `h3_gateway_api_key.txt` in the ComfyUI user directory. This is a one-time setup per machine and applies to every workflow.

MiniMax H3 Image needs a personal API key from the Account page. The gateway's shared key is refused with a permission error for this model.

The file is read on every run, so dropping it in takes effect without restarting.

If the key is missing, the node fails immediately and tells you the registration URL and the exact file path it looked at.

The gateway serves its image and video models from one account, so a personal key already configured for [ComfyUI-AMD-MiniMaxH3](https://github.com/wangxunx/ComfyUI-AMD-MiniMaxH3) or [ComfyUI-AMD-Qwen-Image-2.1](https://github.com/wangxunx/ComfyUI-AMD-Qwen-Image-2.1) works here with no further setup.

### Windows, with the ComfyUI Desktop app

Desktop keeps the user directory at `user` inside its install folder. That folder moves between Desktop versions and depends on what you picked during setup, so the reliable way to find it is to run the node once with no key: the error names the exact file it looked for. On one Windows install it is

```
C:\Users\<you>\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\h3_gateway_api_key.txt
```

Create the file there, paste the key, and save. Notepad's default encoding is fine.

Two Windows details: if File Explorer hides known extensions, **New > Text Document** already ends in `.txt`, so do not type the extension again. And do not create the file with `echo your-key > h3_gateway_api_key.txt` in Windows PowerShell, which writes UTF-16 that the node cannot read.

## Node

| Node | Inputs |
|---|---|
| AMD MiniMax H3 Image | `prompt`, `aspect_ratio` (six ratios), `seed`, `images` (0-3 reference images), `size` (`1K` or `2K`) |

One node covers both tasks. Connect nothing to `images` and it generates from the prompt alone;
connect one to three reference images and the same node edits or combines them. A prompt is always
required, up to 8,000 characters. Extra `image_N` sockets appear as you fill the existing ones.

Refer to the references in the prompt by connection order: `@Image1`, `@Image2`, `@Image3`, the
same convention as ComfyUI's built-in MiniMax H3 nodes. Referencing an image that is not connected
fails before anything is sent.

`size` sets the resolution: `1K` is about 1MP, for example 1024x1024 or 1344x768 for 16:9; `2K` is
about 4MP, for example 2048x2048 or 2688x1536 for 16:9. Both apply to edits too, and the output is
reframed to `aspect_ratio` rather than keeping the shape of the reference images. Steps and guidance are fixed by the gateway, and negative prompts are not supported, so the
node has no inputs for them.

The same prompt, settings and `seed` give the same image. `seed` changes after every run, like
KSampler's; set its control to `fixed` to keep a seed. When editing an image you generated, use a
different seed from the one that made it: the same noise sharpens the image on every pass.

Each image costs 4 credits at `1K` and 16 credits at `2K`. Text to image and single-image edits usually take 15 to 30 seconds. The first request at a resolution the backend has not served before takes noticeably longer because it compiles convolution kernels on the spot; that path is slow, not failing.

### Differences from the built-in MiniMax H3 Image node

| | Built-in partner node | This node |
|---|---|---|
| Models | `MiniMax-H3-Image`, `MiniMax-H3-Image-Highspeed` | `MiniMax-H3-Image` |
| Size | 2K, 4K or custom, ratio can be `auto` | 1K or 2K, six fixed ratios |
| Reference images | up to 16 | up to 3 |
| Prompt enhancement, `revised_prompt` output | yes | no |
| Seed | re-run trigger only | reproducible |

## Example workflows

In ComfyUI, open the template browser from the left sidebar, scroll to the **EXTENSIONS** section, and pick `ComfyUI-AMD-MiniMax-H3-Image`. Both workflows run as-is once your key is configured, and each includes a note explaining the key setup.

| Workflow | What it does |
|---|---|
| `AMD MiniMax H3 Image Text to Image` | Generates a backlit 2K portrait from a detailed prompt that spells out the framing, light and focus. One run costs 16 credits; switch `size` to `1K` for 4-credit drafts |
| `AMD MiniMax H3 Image Edit` | Generates a street portrait, then restages it as a snowy neon night by referring to it as `@Image1`. Replace the first node with **Load Image** to edit your own photo. One run costs 8 credits |

## Your API key never enters a workflow

The node deliberately has no `api_key` widget. Widget values are serialized into workflow JSON and embedded into output image metadata, which would leak the key as soon as a workflow or a generated image is shared. Reading the key from a file outside the graph keeps it out of both.

## License

MIT. See [LICENSE](LICENSE).
