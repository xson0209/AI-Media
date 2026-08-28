from backend import models
from backend.services import source_package


def test_source_package_exports_ai_video_blocks_in_order_and_truncates():
    package = source_package.build_source_package(
        source_kind="manual",
        source_ref_id="source-1",
        source_revision=1,
        blocks=[
            source_package.SourcePackageBlock(block_type="style_notes", sort_order=2, content="visual"),
            source_package.SourcePackageBlock(block_type="idea", sort_order=1, content="x" * 40),
        ],
    )

    blocks = source_package.to_ai_video_source_blocks(package, max_content_chars=20)

    assert [block["block_type"] for block in blocks] == ["idea", "style_notes"]
    assert len(blocks[0]["content"]) <= 20
    assert blocks[0]["content"].endswith("...[truncated]")
    assert blocks[1]["content"] == "visual"
    assert package.fingerprint


def test_source_package_default_limit_matches_ai_video_source_block_schema():
    package = source_package.build_source_package(
        source_kind="manual",
        source_ref_id="source-1",
        source_revision=1,
        blocks=[
            source_package.SourcePackageBlock(
                block_type="rough_script",
                sort_order=1,
                content="x" * (source_package.DEFAULT_AI_VIDEO_BLOCK_LIMIT + 50),
            ),
        ],
    )

    block = source_package.to_ai_video_source_blocks(package)[0]

    assert len(block["content"]) <= source_package.DEFAULT_AI_VIDEO_BLOCK_LIMIT
    assert block["content"].endswith("...[truncated]")
    models.VideoSourceBlockDraft(block_type=block["block_type"], content=block["content"])
