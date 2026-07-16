from backend.services import source_package


def test_source_package_exports_ai_video_blocks_in_order_and_truncates():
    package = source_package.build_source_package(
        source_kind="manual",
        source_ref_id="source-1",
        source_revision=1,
        blocks=[
            source_package.SourcePackageBlock(block_type="style_notes", sort_order=2, content="visual"),
            source_package.SourcePackageBlock(block_type="idea", sort_order=1, content="x" * 20),
        ],
    )

    blocks = source_package.to_ai_video_source_blocks(package, max_content_chars=8)

    assert [block["block_type"] for block in blocks] == ["idea", "style_notes"]
    assert blocks[0]["content"].endswith("...[truncated]")
    assert blocks[1]["content"] == "visual"
    assert package.fingerprint
