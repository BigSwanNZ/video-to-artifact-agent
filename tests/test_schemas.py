from video_to_artifact_agent.schemas import RuntimeCapability


def test_runtime_capability_manifest() -> None:
    capability = RuntimeCapability(
        runtime="mac-mlx",
        model="openbmb/MiniCPM-V-4.6",
        supports_video_url=True,
        supports_local_video=True,
        supports_image=True,
        max_num_frames=128,
    )

    assert capability.supports_video_url is True
    assert capability.privacy == "local"

