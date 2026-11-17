"""Graph builders. Every graph here was measured on this host (see SETUP_LOG.md).

Each builder returns a ComfyUI API-format prompt dict. Node ids are assigned in creation
order, so graphs are stable and diffable.
"""
from __future__ import annotations


class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self._next = 0

    def add(self, class_type: str, **inputs) -> str:
        self._next += 1
        nid = str(self._next)
        self.nodes[nid] = {"class_type": class_type, "inputs": inputs}
        return nid

    @staticmethod
    def ref(nid: str, slot: int = 0):
        return [nid, slot]

    def build(self) -> dict:
        return self.nodes


def _save_image(g: Graph, images: str, prefix: str) -> str:
    return g.add("SaveImage", images=g.ref(images), filename_prefix=prefix)


def _save_video(g: Graph, video: str, prefix: str) -> str:
    return g.add("SaveVideo", video=g.ref(video), filename_prefix=prefix,
                 format="mp4", codec="h264")


def _text_node(g: Graph, clip: str, text: str, zero_out: bool = False) -> str:
    if zero_out:
        return g.add("ConditioningZeroOut", conditioning=g.ref(g.add(
            "CLIPTextEncode", text="", clip=g.ref(clip))))
    return g.add("CLIPTextEncode", text=text, clip=g.ref(clip))


# --------------------------------------------------------------------------- images
def image(lane: dict, prompt: str, negative: str | None, width: int, height: int,
          seed: int, prefix: str) -> dict:
    g = Graph()
    if lane["engine"] == "zimage":
        unet = g.add("UNETLoader", unet_name=lane["unet"], weight_dtype="default")
        clip = g.add("CLIPLoader", clip_name=lane["clip"], type=lane["clip_type"])
        vae = g.add("VAELoader", vae_name=lane["vae"])
        model = g.add("ModelSamplingAuraFlow", model=g.ref(unet), shift=lane["shift"])
        pos = g.add("CLIPTextEncode", text=prompt, clip=g.ref(clip))
        neg = _text_node(g, clip, negative or "", zero_out=not negative)
        latent = g.add("EmptySD3LatentImage", width=width, height=height, batch_size=1)
        sampled = g.add("KSampler", model=g.ref(model), seed=seed, steps=lane["steps"],
                        cfg=lane["cfg"], sampler_name=lane["sampler"],
                        scheduler=lane["scheduler"], positive=g.ref(pos),
                        negative=g.ref(neg), latent_image=g.ref(latent), denoise=1.0)
    elif lane["engine"] == "flux2":
        unet = g.add("UNETLoader", unet_name=lane["unet"], weight_dtype="default")
        clip = g.add("CLIPLoader", clip_name=lane["clip"], type=lane["clip_type"])
        vae = g.add("VAELoader", vae_name=lane["vae"])
        pos = g.add("CLIPTextEncode", text=prompt, clip=g.ref(clip))
        neg = _text_node(g, clip, negative or "", zero_out=not negative)
        guider = g.add("CFGGuider", model=g.ref(unet), positive=g.ref(pos),
                       negative=g.ref(neg), cfg=lane["cfg"])
        sigmas = g.add("Flux2Scheduler", steps=lane["steps"], width=width, height=height)
        sampler = g.add("KSamplerSelect", sampler_name=lane["sampler"])
        noise = g.add("RandomNoise", noise_seed=seed)
        latent = g.add("EmptyFlux2LatentImage", width=width, height=height, batch_size=1)
        sampled = g.add("SamplerCustomAdvanced", noise=g.ref(noise), guider=g.ref(guider),
                        sampler=g.ref(sampler), sigmas=g.ref(sigmas),
                        latent_image=g.ref(latent))
    else:
        raise ValueError(f"unknown image engine {lane['engine']!r}")

    decoded = g.add("VAEDecode", samples=g.ref(sampled), vae=g.ref(vae))
    _save_image(g, decoded, prefix)
    return g.build()


def image_ref(lane: dict, prompt: str, refs: list[str], width: int, height: int,
              seed: int, prefix: str) -> dict:
    """FLUX.2-Klein with reference images (character sheet, location plate, prop).

    Each reference is VAE-encoded and chained onto both conditionings with ReferenceLatent,
    exactly as the bundled Klein image-edit template does. The prompt addresses them as
    "image 1", "image 2", ... in the order given.
    """
    g = Graph()
    unet = g.add("UNETLoader", unet_name=lane["unet"], weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name=lane["clip"], type=lane["clip_type"])
    vae = g.add("VAELoader", vae_name=lane["vae"])
    pos = g.add("CLIPTextEncode", text=prompt, clip=g.ref(clip))
    neg = g.add("ConditioningZeroOut", conditioning=g.ref(pos))
    for name in refs:
        img = g.add("LoadImage", image=name)
        scaled = g.add("ImageScaleToTotalPixels", image=g.ref(img), upscale_method="lanczos",
                       megapixels=lane["ref_megapixels"], resolution_steps=1)
        lat = g.add("VAEEncode", pixels=g.ref(scaled), vae=g.ref(vae))
        pos = g.add("ReferenceLatent", conditioning=g.ref(pos), latent=g.ref(lat))
        neg = g.add("ReferenceLatent", conditioning=g.ref(neg), latent=g.ref(lat))
    guider = g.add("CFGGuider", model=g.ref(unet), positive=g.ref(pos),
                   negative=g.ref(neg), cfg=lane["cfg"])
    sigmas = g.add("Flux2Scheduler", steps=lane["steps"], width=width, height=height)
    sampler = g.add("KSamplerSelect", sampler_name=lane["sampler"])
    noise = g.add("RandomNoise", noise_seed=seed)
    latent = g.add("EmptyFlux2LatentImage", width=width, height=height, batch_size=1)
    sampled = g.add("SamplerCustomAdvanced", noise=g.ref(noise), guider=g.ref(guider),
                    sampler=g.ref(sampler), sigmas=g.ref(sigmas), latent_image=g.ref(latent))
    decoded = g.add("VAEDecode", samples=g.ref(sampled), vae=g.ref(vae))
    _save_image(g, decoded, prefix)
    return g.build()


# --------------------------------------------------------------------------- LTX video
def _ltx_common(g: Graph, lane: dict, prompt: str, negative: str, fps: float):
    unet = g.add("UNETLoader", unet_name=lane["unet"], weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name=lane["clip"], type=lane["clip_type"])
    vae_v = g.add("VAELoader", vae_name=lane["vae_video"])
    vae_a = g.add("VAELoader", vae_name=lane["vae_audio"])
    pos = g.add("CLIPTextEncode", text=prompt, clip=g.ref(clip))
    neg = g.add("CLIPTextEncode", text=negative, clip=g.ref(clip))
    cond = g.add("LTXVConditioning", positive=g.ref(pos), negative=g.ref(neg), frame_rate=fps)
    return unet, vae_v, vae_a, cond


def ltx(lane: dict, prompt: str, negative: str, width: int, height: int, length: int,
        fps: float, seed: int, prefix: str) -> dict:
    g = Graph()
    unet, vae_v, vae_a, cond = _ltx_common(g, lane, prompt, negative, fps)

    video_lat = g.add("EmptyLTXVLatentVideo", width=width, height=height,
                      length=length, batch_size=1)
    audio_lat = g.add("LTXVEmptyLatentAudio", frames_number=length, frame_rate=25.0,
                      batch_size=1, audio_vae=g.ref(vae_a))
    av = g.add("LTXVConcatAVLatent", video_latent=g.ref(video_lat),
               audio_latent=g.ref(audio_lat))

    sig1 = lane["sigmas"] if not lane.get("two_pass") else lane["sigmas1"]
    noise1 = g.add("RandomNoise", noise_seed=seed)
    sel1 = g.add("KSamplerSelect", sampler_name=lane["sampler"])
    sigmas1 = g.add("ManualSigmas", sigmas=sig1)
    guider1 = g.add("LTXVDualCFGGuider", model=g.ref(unet), positive=g.ref(cond),
                    negative=g.ref(cond, 1), video_cfg=lane["video_cfg"],
                    audio_cfg=lane["audio_cfg"])
    pass1 = g.add("SamplerCustomAdvanced", noise=g.ref(noise1), guider=g.ref(guider1),
                  sampler=g.ref(sel1), sigmas=g.ref(sigmas1), latent_image=g.ref(av))
    split1 = g.add("LTXVSeparateAVLatent", av_latent=g.ref(pass1))

    if lane.get("two_pass"):
        up_model = g.add("LatentUpscaleModelLoader", model_name=lane["upscale_model"])
        up = g.add("LTXVLatentUpsampler", samples=g.ref(split1),
                   upscale_model=g.ref(up_model), vae=g.ref(vae_v))
        av2 = g.add("LTXVConcatAVLatent", video_latent=g.ref(up),
                    audio_latent=g.ref(split1, 1))
        noise2 = g.add("RandomNoise", noise_seed=seed + 1)
        sel2 = g.add("KSamplerSelect", sampler_name=lane["sampler"])
        sigmas2 = g.add("ManualSigmas", sigmas=lane["sigmas2"])
        guider2 = g.add("LTXVDualCFGGuider", model=g.ref(unet), positive=g.ref(cond),
                        negative=g.ref(cond, 1), video_cfg=lane["video_cfg"],
                        audio_cfg=lane["audio_cfg"])
        pass2 = g.add("SamplerCustomAdvanced", noise=g.ref(noise2), guider=g.ref(guider2),
                      sampler=g.ref(sel2), sigmas=g.ref(sigmas2), latent_image=g.ref(av2))
        split2 = g.add("LTXVSeparateAVLatent", av_latent=g.ref(pass2))
        src = split2
    else:
        src = split1

    images = g.add("VAEDecodeTiled", samples=g.ref(src), vae=g.ref(vae_v),
                   tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
    audio = g.add("LTXVAudioVAEDecode", samples=g.ref(src, 1), audio_vae=g.ref(vae_a))
    video = g.add("CreateVideo", images=g.ref(images), fps=fps, audio=g.ref(audio))
    _save_video(g, video, prefix)
    return g.build()


def ltx_i2v(lane: dict, prompt: str, negative: str, image: str, width: int, height: int,
            length: int, fps: float, seed: int, prefix: str,
            audio: str | None = None) -> dict:
    """LTX-2.5 two-pass from a start keyframe; optionally driven by a speech wav.

    Wiring follows the bundled `video_ltx2_5_i2v` template: the keyframe is pinned into the
    draft latent at strength `i2v_strength1`, the draft is latent-upscaled x2, the keyframe
    is pinned again at full strength, and a short second pass refines.

    With `audio`, the wav is encoded by the audio VAE and frozen with a zero noise mask
    (the `ia2v` template's trick), so the model animates the picture *to* the given speech -
    lip-sync at production resolution. The original wav, not the VAE round trip, is muxed.
    `width`/`height` are the draft size; the output is twice that.
    """
    g = Graph()
    unet, vae_v, vae_a, cond = _ltx_common(g, lane, prompt, negative, fps)
    model = unet
    if audio and lane.get("modality_scale"):
        model = g.add("LTXVModalityGuidance", model=g.ref(unet),
                      modality_scale=lane["modality_scale"], start_percent=0.0,
                      end_percent=1.0)

    img = g.add("LoadImage", image=image)
    fitted = g.add("ImageScale", image=g.ref(img), upscale_method="lanczos",
                   width=width * 2, height=height * 2, crop="center")
    pre = g.add("LTXVPreprocess", image=g.ref(fitted), img_compression=lane["img_compression"])

    empty = g.add("EmptyLTXVLatentVideo", width=width, height=height, length=length,
                  batch_size=1)
    video_lat = g.add("LTXVImgToVideoInplace", vae=g.ref(vae_v), image=g.ref(pre),
                      latent=g.ref(empty), strength=lane["i2v_strength1"], bypass=False)
    if audio:
        snd = g.add("LoadAudio", audio=audio)
        enc = g.add("LTXVAudioVAEEncode", audio=g.ref(snd), audio_vae=g.ref(vae_a))
        mask = g.add("SolidMask", value=0.0, width=width, height=height)
        audio_lat = g.add("SetLatentNoiseMask", samples=g.ref(enc), mask=g.ref(mask))
    else:
        snd = None
        audio_lat = g.add("LTXVEmptyLatentAudio", frames_number=length, frame_rate=fps,
                          batch_size=1, audio_vae=g.ref(vae_a))
    av = g.add("LTXVConcatAVLatent", video_latent=g.ref(video_lat),
               audio_latent=g.ref(audio_lat))

    noise1 = g.add("RandomNoise", noise_seed=seed)
    sel1 = g.add("KSamplerSelect", sampler_name=lane["sampler"])
    sigmas1 = g.add("ManualSigmas", sigmas=lane["sigmas1"])
    guider1 = g.add("LTXVDualCFGGuider", model=g.ref(model), positive=g.ref(cond),
                    negative=g.ref(cond, 1), video_cfg=lane["video_cfg"],
                    audio_cfg=lane["audio_cfg"])
    pass1 = g.add("SamplerCustomAdvanced", noise=g.ref(noise1), guider=g.ref(guider1),
                  sampler=g.ref(sel1), sigmas=g.ref(sigmas1), latent_image=g.ref(av))
    split1 = g.add("LTXVSeparateAVLatent", av_latent=g.ref(pass1))

    up_model = g.add("LatentUpscaleModelLoader", model_name=lane["upscale_model"])
    up = g.add("LTXVLatentUpsampler", samples=g.ref(split1), upscale_model=g.ref(up_model),
               vae=g.ref(vae_v))
    up_pinned = g.add("LTXVImgToVideoInplace", vae=g.ref(vae_v), image=g.ref(pre),
                      latent=g.ref(up), strength=lane["i2v_strength2"], bypass=False)
    av2 = g.add("LTXVConcatAVLatent", video_latent=g.ref(up_pinned),
                audio_latent=g.ref(split1, 1))
    noise2 = g.add("RandomNoise", noise_seed=seed + 1)
    sel2 = g.add("KSamplerSelect", sampler_name=lane["sampler"])
    sigmas2 = g.add("ManualSigmas", sigmas=lane["sigmas2"])
    guider2 = g.add("LTXVDualCFGGuider", model=g.ref(model), positive=g.ref(cond),
                    negative=g.ref(cond, 1), video_cfg=lane["video_cfg"],
                    audio_cfg=lane["audio_cfg"])
    pass2 = g.add("SamplerCustomAdvanced", noise=g.ref(noise2), guider=g.ref(guider2),
                  sampler=g.ref(sel2), sigmas=g.ref(sigmas2), latent_image=g.ref(av2))
    split2 = g.add("LTXVSeparateAVLatent", av_latent=g.ref(pass2))

    images = g.add("VAEDecodeTiled", samples=g.ref(split2), vae=g.ref(vae_v),
                   tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
    if snd:
        video = g.add("CreateVideo", images=g.ref(images), fps=fps, audio=g.ref(snd))
    else:
        dec = g.add("LTXVAudioVAEDecode", samples=g.ref(split2, 1), audio_vae=g.ref(vae_a))
        video = g.add("CreateVideo", images=g.ref(images), fps=fps, audio=g.ref(dec))
    _save_video(g, video, prefix)
    return g.build()


# --------------------------------------------------------------------------- Wan
def wan_t2v(lane: dict, prompt: str, negative: str, width: int, height: int, length: int,
            fps: float, seed: int, prefix: str) -> dict:
    g = Graph()
    unet = g.add("UNETLoader", unet_name=lane["unet"], weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name=lane["clip"], type=lane["clip_type"])
    vae = g.add("VAELoader", vae_name=lane["vae"])
    pos = g.add("CLIPTextEncode", text=prompt, clip=g.ref(clip))
    neg = g.add("CLIPTextEncode", text=negative, clip=g.ref(clip))
    model = g.add("ModelSamplingSD3", model=g.ref(unet), shift=lane["shift"])
    latent = g.add("Wan22ImageToVideoLatent", vae=g.ref(vae), width=width,
                   height=height, length=length, batch_size=1)
    sampled = g.add("KSampler", model=g.ref(model), seed=seed, steps=lane["steps"],
                    cfg=lane["cfg"], sampler_name=lane["sampler"],
                    scheduler=lane["scheduler"], positive=g.ref(pos),
                    negative=g.ref(neg), latent_image=g.ref(latent), denoise=1.0)
    decoded = g.add("VAEDecode", samples=g.ref(sampled), vae=g.ref(vae))
    video = g.add("CreateVideo", images=g.ref(decoded), fps=fps)
    _save_video(g, video, prefix)
    return g.build()


def s2v(lane: dict, prompt: str, negative: str, ref_image: str, audio: str,
        width: int, height: int, length: int, seed: int, prefix: str,
        with_audio: bool = True) -> dict:
    g = Graph()
    unet = g.add("UNETLoader", unet_name=lane["unet"], weight_dtype="default")
    model = unet
    if lane.get("lora"):
        model = g.add("LoraLoaderModelOnly", model=g.ref(unet),
                      lora_name=lane["lora"], strength_model=lane["lora_strength"])
    sampled_model = g.add("ModelSamplingSD3", model=g.ref(model), shift=lane["shift"])
    clip = g.add("CLIPLoader", clip_name=lane["clip"], type=lane["clip_type"])
    vae = g.add("VAELoader", vae_name=lane["vae"])
    pos = g.add("CLIPTextEncode", text=prompt, clip=g.ref(clip))
    neg = g.add("CLIPTextEncode", text=negative, clip=g.ref(clip))
    enc = g.add("AudioEncoderLoader", audio_encoder_name=lane["audio_encoder"])
    snd = g.add("LoadAudio", audio=audio)
    encoded = g.add("AudioEncoderEncode", audio_encoder=g.ref(enc), audio=g.ref(snd))
    img = g.add("LoadImage", image=ref_image)
    cond = g.add("WanSoundImageToVideo", positive=g.ref(pos), negative=g.ref(neg),
                 vae=g.ref(vae), width=width, height=height, length=length,
                 batch_size=1, audio_encoder_output=g.ref(encoded), ref_image=g.ref(img))
    sampled = g.add("KSampler", model=g.ref(sampled_model), seed=seed, steps=lane["steps"],
                    cfg=lane["cfg"], sampler_name=lane["sampler"],
                    scheduler=lane["scheduler"], positive=g.ref(cond),
                    negative=g.ref(cond, 1), latent_image=g.ref(cond, 2), denoise=1.0)
    decoded = g.add("VAEDecode", samples=g.ref(sampled), vae=g.ref(vae))
    if with_audio:
        video = g.add("CreateVideo", images=g.ref(decoded), fps=lane["fps"],
                      audio=g.ref(snd))
    else:
        video = g.add("CreateVideo", images=g.ref(decoded), fps=lane["fps"])
    _save_video(g, video, prefix)
    return g.build()


def animate(lane: dict, prompt: str, negative: str, ref_image: str, drive_video: str,
            width: int, height: int, length: int, seed: int, prefix: str) -> dict:
    g = Graph()
    unet = g.add("UNETLoader", unet_name=lane["unet"], weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name=lane["clip"], type=lane["clip_type"])
    vae = g.add("VAELoader", vae_name=lane["vae"])
    vision = g.add("CLIPVisionLoader", clip_name=lane["clip_vision"])
    pos = g.add("CLIPTextEncode", text=prompt, clip=g.ref(clip))
    neg = g.add("CLIPTextEncode", text=negative, clip=g.ref(clip))
    img = g.add("LoadImage", image=ref_image)
    vid = g.add("LoadVideo", file=drive_video)
    parts = g.add("GetVideoComponents", video=g.ref(vid))
    venc = g.add("CLIPVisionEncode", clip_vision=g.ref(vision), image=g.ref(img), crop="none")
    cond = g.add("WanAnimateToVideo", positive=g.ref(pos), negative=g.ref(neg),
                 vae=g.ref(vae), width=width, height=height, length=length, batch_size=1,
                 continue_motion_max_frames=5, video_frame_offset=0,
                 clip_vision_output=g.ref(venc), reference_image=g.ref(img),
                 pose_video=g.ref(parts))
    model = g.add("ModelSamplingSD3", model=g.ref(unet), shift=lane["shift"])
    sampled = g.add("KSampler", model=g.ref(model), seed=seed, steps=lane["steps"],
                    cfg=lane["cfg"], sampler_name=lane["sampler"],
                    scheduler=lane["scheduler"], positive=g.ref(cond),
                    negative=g.ref(cond, 1), latent_image=g.ref(cond, 2), denoise=1.0)
    trimmed = g.add("TrimVideoLatent", samples=g.ref(sampled), trim_amount=g.ref(cond, 3))
    decoded = g.add("VAEDecode", samples=g.ref(trimmed), vae=g.ref(vae))
    video = g.add("CreateVideo", images=g.ref(decoded), fps=lane["fps"])
    _save_video(g, video, prefix)
    return g.build()


BUILDERS = {
    "zimage": image,
    "flux2": image,
    "flux2_ref": image_ref,
    "ltx": ltx,
    "ltx_i2v": ltx_i2v,
    "wan_t2v": wan_t2v,
    "s2v": s2v,
    "animate": animate,
}
