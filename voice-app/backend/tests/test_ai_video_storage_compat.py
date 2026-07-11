from backend import config
from backend.services import video_storage


def test_ai_video_artifact_paths_survive_data_dir_refactor(tmp_path):
    previous_data_dir = config.get_data_dir()
    try:
        config.set_data_dir(tmp_path)
        subtitle_path = video_storage.get_project_subdir("project-1", "subtitles") / "subtitle.srt"
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")

        stored_path = video_storage.to_artifact_storage_path(subtitle_path)
        resolved_path = video_storage.resolve_artifact_storage_path(stored_path)

        assert stored_path == "video_projects/project-1/subtitles/subtitle.srt"
        assert resolved_path == subtitle_path.resolve()
        assert resolved_path.read_text(encoding="utf-8").startswith("1\n")
    finally:
        config.set_data_dir(previous_data_dir)
