# NghiÃªn cá»©u thiáº¿t káº¿ route Content Tools

NgÃ y kháº£o sÃ¡t: 2026-10-04
Pháº¡m vi: má»™t route má»›i gom ba luá»“ng **Podcast â†’ video ngáº¯n**, **Má»™t ná»™i dung â†’ nhiá»u gÃ³c ká»ƒ**, vÃ  **Má»™t bÃ i há»c â†’ truyá»‡n minh há»a**.

## Káº¿t luáº­n

NÃªn táº¡o má»™t workspace frontend `/content-tools` vÃ  má»™t boundary backend `/content-tools`, dÃ¹ng chung má»™t job model vÃ  má»™t output contract. Ba lá»±a chá»n chá»‰ thay Ä‘á»•i adapter Ä‘áº§u vÃ o vÃ  profile sÃ¡ng táº¡o; khÃ´ng nÃªn táº¡o ba route hoáº·c ba báº£ng dá»¯ liá»‡u Ä‘á»™c láº­p.

MVP nÃªn cháº¡y theo chuá»—i:

```text
Chá»n tool â†’ nháº­p nguá»“n â†’ chuáº©n hÃ³a nguá»“n â†’ táº¡o transcript/context â†’ táº¡o brief â†’ sinh cÃ¡c gÃ³c ká»ƒ hoáº·c truyá»‡n â†’ táº¡o scene + prompt video â†’ duyá»‡t â†’ handoff sang AI Video
```

Podcast lÃ  pháº§n cáº§n bá»• sung backend rÃµ nháº¥t. `video-inspiration` hiá»‡n há»— trá»£ upload `.mp4` vÃ  cÃ³ cá» `allow_audio_only` á»Ÿ bÆ°á»›c phÃ¢n tÃ­ch, nhÆ°ng `create_upload_job` tá»« chá»‘i má»i Ä‘uÃ´i khÃ¡c `.mp4`. CÃ³ thá»ƒ tÃ¡i sá»­ dá»¥ng STT, AI planning, source blocks vÃ  handoff hiá»‡n cÃ³ sau khi thÃªm adapter audio; khÃ´ng nÃªn giáº£ vá» coi file podcast lÃ  video.

## Nhá»¯ng gÃ¬ Ä‘Ã£ xÃ¡c nháº­n trong repository

### Fact

- React dÃ¹ng TanStack Router. CÃ¡c workspace lá»›n Ä‘Ã£ Ä‘Æ°á»£c khai bÃ¡o trong [`app/src/router.tsx`](../../app/src/router.tsx), gá»“m `/ai-video`, `/video-inspiration`, `/research`, `/comic-series-analysis` vÃ  `/product-video`.
- Backend Ä‘Äƒng kÃ½ router táº­p trung táº¡i [`backend/routes/__init__.py`](../../backend/routes/__init__.py). CÃ¡c boundary liÃªn quan lÃ  `/research`, `/video-inspiration` vÃ  `/transcribe`.
- Research Workspace Ä‘Ã£ cÃ³ project, source, run, idea, script, score, chat vÃ  handoff sang AI Video. Contract náº±m trong [`backend/models.py`](../../backend/models.py), route trong [`backend/routes/research.py`](../../backend/routes/research.py), service trong [`backend/services/research.py`](../../backend/services/research.py).
- Research source type hiá»‡n gá»“m `video_url`, `video_upload`, `story_url`, `image_upload`, `screenshot_upload`, `github_repo`, `text`, `docs_url`, `series_memory`. KhÃ´ng cÃ³ `audio_upload`, `audio_url` hoáº·c podcast feed.
- Video Inspiration Ä‘Ã£ cÃ³ transcript, frame/shot/audio event, retention beat, rewrite candidates, variant stages, structured handoff vÃ  táº¡o AI Video project. Contract chÃ­nh lÃ  `VideoInspirationJobResponse` vÃ  cÃ¡c endpoint trong [`backend/routes/video_inspiration.py`](../../backend/routes/video_inspiration.py).
- `POST /video-inspiration/jobs/upload` chá»‰ nháº­n MP4 trong [`backend/services/video_inspiration.py`](../../backend/services/video_inspiration.py). PhÃ¢n tÃ­ch cÃ³ thá»ƒ bá» qua vision khi `allow_audio_only=true`, nhÆ°ng bÆ°á»›c Ä‘áº§u váº«n yÃªu cáº§u má»™t job video.
- `POST /transcribe` nháº­n audio extensions `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.webm`, `.opus`; route dÃ¹ng Whisper backend hiá»‡n cÃ³ trong [`backend/routes/transcription.py`](../../backend/routes/transcription.py).
- Research Ä‘Ã£ cÃ³ flow input text/URL/upload vÃ  UI `SourcePanel`; API client hiá»‡n cÃ³ cÃ¡c method research tÆ°Æ¡ng á»©ng.
- AI Video handoff cÃ³ thá»ƒ nháº­n `target_language`, `target_duration_seconds`, `aspect_ratio`, `content_genre` vÃ  source blocks. ÄÃ¢y lÃ  Ä‘iá»ƒm ná»‘i chung cho cáº£ ba tool.

### Assumption

- â€œPodcast â†’ video ngáº¯nâ€ nghÄ©a lÃ  trÃ­ch Ä‘oáº¡n Ã¢m thanh cÃ³ Ã½ nghÄ©a, táº¡o hook/ká»‹ch báº£n ngáº¯n, rá»“i táº¡o shot prompts; MVP chÆ°a cáº§n tá»± Ä‘Äƒng lÃªn ná»n táº£ng.
- â€œNhiá»u gÃ³c ká»ƒâ€ nghÄ©a lÃ  sinh cÃ¡c biáº¿n thá»ƒ cÃ¹ng giá»¯ content spine vÃ  nguá»“n gá»‘c, khÃ´ng pháº£i viáº¿t láº¡i tÃ¹y Ã½ lÃ m sai thÃ´ng tin.
- â€œBÃ i há»c â†’ truyá»‡n minh há»aâ€ cáº§n giá»¯ má»¥c tiÃªu bÃ i há»c vÃ  biáº¿n nÃ³ thÃ nh hÃ nh Ä‘á»™ng/xung Ä‘á»™t/káº¿t quáº£ trong má»™t cÃ¢u chuyá»‡n ngáº¯n.
- NgÆ°á»i dÃ¹ng muá»‘n cÃ¹ng má»™t route Ä‘á»ƒ dá»… má»Ÿ rá»™ng thÃªm loáº¡i nguyÃªn liá»‡u sau nÃ y.

### Unknown cáº§n chá»‘t trÆ°á»›c khi má»Ÿ rá»™ng

- Podcast URL sáº½ há»— trá»£ RSS feed, direct audio URL, hay cáº£ trang web podcast? RSS vÃ  direct enclosure cÃ³ thá»ƒ tá»± Ä‘á»™ng hÃ³a Ä‘Ã¡ng tin hÆ¡n trang web.
- Äá»™ dÃ i tá»‘i Ä‘a file/audio vÃ  chiáº¿n lÆ°á»£c táº£i file lá»›n (stream/chunk/background) chÆ°a Ä‘Æ°á»£c quy Ä‘á»‹nh.
- Output cuá»‘i lÃ  chá»‰ prompt/scene plan hay tá»± Ä‘á»™ng táº¡o project AI Video ngay? Äá» xuáº¥t máº·c Ä‘á»‹nh lÃ  táº¡o draft vÃ  yÃªu cáº§u duyá»‡t trÆ°á»›c handoff.
- â€œNhiá»u gÃ³c ká»ƒâ€ cÃ³ cáº§n sá»‘ lÆ°á»£ng biáº¿n thá»ƒ cá»‘ Ä‘á»‹nh (vÃ­ dá»¥ 5) hay cho ngÆ°á»i dÃ¹ng chá»n 2â€“8?

## Nguá»“n sÆ¡ cáº¥p vÃ  Ã½ nghÄ©a thiáº¿t káº¿

1. **RSS 2.0 Specification** â€” [rssboard.org/rss-specification](https://www.rssboard.org/rss-specification) mÃ´ táº£ má»™t RSS document cÃ³ má»™t `channel`, trong Ä‘Ã³ cÃ³ metadata vÃ  cÃ¡c `item`; item/channel cÃ³ URL, title, description vÃ  thÃ´ng tin ngÃ y phÃ¡t hÃ nh. Feed adapter nÃªn lÆ°u URL feed, item GUID/title/pubDate vÃ  enclosure URL, khÃ´ng chá»‰ lÆ°u HTML Ä‘Ã£ scrape.
2. **FastAPI file uploads** â€” [FastAPI Request Files](https://fastapi.tiangolo.com/tutorial/request-files/) mÃ´ táº£ `UploadFile` vÃ  `multipart/form-data`. Route upload audio nÃªn dÃ¹ng `UploadFile`, kiá»ƒm tra MIME/Ä‘uÃ´i vÃ  giá»›i háº¡n kÃ­ch thÆ°á»›c trÆ°á»›c khi ghi storage; khÃ´ng Ä‘á»c khÃ´ng giá»›i háº¡n vÃ o RAM.
3. **TanStack Router route tree** â€” [TanStack Router route trees](https://tanstack.com/router/latest/docs/framework/react/guide/route-trees) lÃ  tÃ i liá»‡u chÃ­nh thá»©c vá» route tree vÃ  component route. Route frontend má»›i nÃªn Ä‘Æ°á»£c thÃªm vÃ o route tree hiá»‡n táº¡i, giá»¯ `RootLayout` vÃ  cá» `isWideWorkspace` Ä‘á»ƒ cÃ³ hÃ nh vi layout nháº¥t quÃ¡n.
4. **Nguá»“n chÃ­nh trong repo** â€” `backend/routes/research.py`, `backend/routes/video_inspiration.py`, `backend/routes/transcription.py`, `backend/services/video_inspiration.py`, `app/src/router.tsx` lÃ  nguá»“n sá»± tháº­t cá»§a contract hiá»‡n hÃ nh. KhÃ´ng táº¡o contract má»›i trÃ¹ng vá»›i cÃ¡c output/handoff Ä‘Ã£ cÃ³ náº¿u cÃ³ thá»ƒ dÃ¹ng adapter.

## PhÆ°Æ¡ng Ã¡n

### PhÆ°Æ¡ng Ã¡n A â€” Má»™t `/content-tools` + job contract chung (Ä‘á» xuáº¥t)

`ContentToolKind` gá»“m `podcast_short`, `story_angles`, `lesson_story`. Má»™t `ContentToolJob` lÆ°u `kind`, `source`, `status`, `progress`, `normalized_context`, `outputs`, `limitations`, `provenance` vÃ  `created_ai_video_project_id`.

Luá»“ng dá»¯ liá»‡u:

```text
ContentToolsPage
  â””â”€ POST /content-tools/jobs
       â””â”€ adapter theo kind
            â”œâ”€ podcast: RSS/direct audio/upload â†’ STT + segment selection
            â”œâ”€ angles: text/url â†’ source context â†’ variants
            â””â”€ lesson: text/url â†’ lesson objective â†’ story beats
       â””â”€ POST /content-tools/jobs/{id}/generate
            â””â”€ output contract: brief, scripts, scenes, prompts
       â””â”€ POST /content-tools/jobs/{id}/handoff
            â””â”€ AI Video project/source blocks
```

Æ¯u Ä‘iá»ƒm: má»™t UI, tráº¡ng thÃ¡i vÃ  retry; dá»… thÃªm `article_to_video`, `image_to_motion`, `comments_to_ideas`; cÃ³ thá»ƒ tÃ¡i sá»­ dá»¥ng handoff vÃ  quality gate. NhÆ°á»£c Ä‘iá»ƒm: cáº§n thiáº¿t káº¿ schema cÃ³ union rÃµ rÃ ng, trÃ¡nh `dict` khÃ´ng kiá»ƒm soÃ¡t.

### PhÆ°Æ¡ng Ã¡n B â€” TÃ¡i sá»­ dá»¥ng Research Workspace, thÃªm mode

DÃ¹ng `/research` hiá»‡n táº¡i, thÃªm cÃ¡c source type/profile vÃ  má»™t tab output. Podcast thÃªm source adapter; hai tool cÃ²n láº¡i dÃ¹ng research run/idea/script.

Æ¯u Ä‘iá»ƒm: Ã­t route má»›i, táº­n dá»¥ng project/source/run/score. NhÆ°á»£c Ä‘iá»ƒm: Research Workspace hiá»‡n thiÃªn vá» nghiÃªn cá»©u nguá»“n vÃ  review; UI sáº½ khÃ³ hiá»ƒu khi biáº¿n thÃ nh tool sÃ¡ng táº¡o trá»±c tiáº¿p, vÃ  podcast cáº§n lifecycle dÃ i hÆ¡n source adapter hiá»‡n táº¡i.

### PhÆ°Æ¡ng Ã¡n C â€” Ba route Ä‘á»™c láº­p

Táº¡o `/podcast-to-video`, `/story-angles`, `/lesson-story` vá»›i schema riÃªng.

Æ¯u Ä‘iá»ƒm: má»—i flow dá»… viáº¿t ban Ä‘áº§u. NhÆ°á»£c Ä‘iá»ƒm: láº·p upload/status/retry/error/handoff/UI, khÃ³ thá»‘ng nháº¥t provenance vÃ  vá» sau tá»‘n chi phÃ­ báº£o trÃ¬. KhÃ´ng khuyáº¿n nghá»‹.

## Contract cáº¥p cao Ä‘á» xuáº¥t

```json
{
  "kind": "podcast_short | story_angles | lesson_story",
  "title": "string",
  "source": {
    "type": "text | url | rss | audio_upload | audio_url",
    "url": "https://...",
    "text": "...",
    "file_ref": "..."
  },
  "target_language": "vi",
  "target_duration_seconds": 60,
  "aspect_ratio": "9:16",
  "variant_count": 3,
  "creative_direction": "...",
  "rights_attested": false
}
```

Response/state nÃªn cÃ³:

```json
{
  "id": "uuid",
  "kind": "podcast_short",
  "status": "draft | ingesting | transcribing | generating | ready_for_review | handoff | failed | cancelled",
  "current_step": "...",
  "progress": 0.0,
  "source_summary": {},
  "outputs": {
    "content_spine": {},
    "variants": [],
    "scenes": [],
    "prompt_pack": {},
    "provenance": []
  },
  "limitations": [],
  "error_code": null,
  "created_ai_video_project_id": null
}
```

CÃ¡c output nÃªn dÃ¹ng shape hiá»‡n cÃ³ cá»§a AI Video: source blocks (`idea`, `rough_script`, `character_notes`, `style_notes`, `must_have`, `avoid`), timeline beats, visual/audio direction. DÃ¹ng `content_spine` vÃ  `source_refs` Ä‘á»ƒ cÃ¡c gÃ³c ká»ƒ khÃ´ng lÃ m máº¥t nguá»“n.

## Quy táº¯c theo tá»«ng tool

### Podcast â†’ video ngáº¯n

- Input: RSS feed, direct audio URL hoáº·c upload audio.
- Ingest: resolve feed/item/enclosure; kiá»ƒm tra scheme, MIME, kÃ­ch thÆ°á»›c, duration; lÆ°u redacted URL + checksum.
- STT: tÃ¡i sá»­ dá»¥ng Whisper route/service; lÆ°u segment start/end, speaker náº¿u cÃ³, confidence/limitations.
- Chá»n Ä‘oáº¡n: Æ°u tiÃªn segment cÃ³ cÃ¢u há»i, claim, xung Ä‘á»™t hoáº·c payoff; báº¯t buá»™c tráº£ vá» `selection_reason` vÃ  timestamp Ä‘á»ƒ ngÆ°á»i dÃ¹ng kiá»ƒm tra.
- Sinh output: 3â€“5 hook, script 30/60 giÃ¢y, shot list vÃ  prompt hÃ¬nh áº£nh/video bá»• trá»£. KhÃ´ng tá»± kháº³ng Ä‘á»‹nh claim ngoÃ i transcript; thÃªm `source_refs`.
- Rights: link/file chá»‰ lÃ  nguá»“n tham kháº£o; cáº§n checkbox ngÆ°á»i dÃ¹ng xÃ¡c nháº­n quyá»n sá»­ dá»¥ng trÆ°á»›c handoff.

### Má»™t ná»™i dung â†’ nhiá»u gÃ³c ká»ƒ

- Input: text, article/story URL hoáº·c source Ä‘Ã£ duyá»‡t trong Research.
- Chuáº©n hÃ³a: giá»¯ `canonical_summary`, claims vÃ  source refs.
- Profiles Ä‘á» xuáº¥t: `how_to`, `story`, `comparison`, `counterpoint`, `q_and_a`; cho phÃ©p chá»n sá»‘ lÆ°á»£ng.
- Má»—i variant pháº£i chá»©a `angle`, `audience`, `hook`, `promise`, `script_outline`, `cta`, `what_changed_from_canonical`.
- Cháº·n biáº¿n thá»ƒ náº¿u thiáº¿u nguá»“n hoáº·c biáº¿n Ä‘á»•i claim; hiá»ƒn thá»‹ cáº£nh bÃ¡o thay vÃ¬ Ã¢m tháº§m viáº¿t má»›i.

### Má»™t bÃ i há»c â†’ truyá»‡n minh há»a

- Input: bÃ i há»c, ká»¹ nÄƒng hoáº·c quy táº¯c á»©ng xá»­.
- Báº¯t buá»™c tÃ¡ch `learning_objective`, `audience`, `success_behavior` trÆ°á»›c khi viáº¿t truyá»‡n.
- Output: nhÃ¢n váº­t/bá»‘i cáº£nh, lá»±a chá»n khÃ³, háº­u quáº£, hÃ nh Ä‘á»™ng Ä‘Ãºng, payoff vÃ  cÃ¢u káº¿t nháº¯c bÃ i há»c; prompt tá»«ng scene.
- Kiá»ƒm tra: ngÆ°á»i xem cÃ³ suy ra hÃ nh vi Ä‘Ãºng tá»« hÃ nh Ä‘á»™ng trong truyá»‡n khÃ´ng; trÃ¡nh biáº¿n bÃ i há»c thÃ nh lá»i giáº£ng dÃ i.
- Náº¿u dÃ¹ng ngÆ°á»i tháº­t/tráº» em hoáº·c nguá»“n cÃ³ báº£n quyá»n, cáº§n rights/safety gate riÃªng.

## Failure modes cáº§n xá»­ lÃ½

- RSS khÃ´ng há»£p lá»‡, feed redirect, item khÃ´ng cÃ³ enclosure, enclosure tráº£ MIME sai hoáº·c háº¿t háº¡n.
- Audio/video quÃ¡ lá»›n, duration vÆ°á»£t giá»›i háº¡n, file giáº£ máº¡o Ä‘uÃ´i; pháº£i giá»›i háº¡n trÆ°á»›c khi lÆ°u vÃ  cháº¡y ffprobe sau khi lÆ°u.
- STT timeout/model chÆ°a táº£i; job pháº£i giá»¯ checkpoint, retry idempotent, khÃ´ng táº¡o output ná»­a vá»i.
- AI provider timeout/429/credential lá»—i; tráº£ `error_code`, lÆ°u attempt metadata, cho phÃ©p retry tá»«ng stage.
- User báº¥m generate/handoff hai láº§n; cáº§n idempotency key hoáº·c khÃ³a job theo `(job_id, operation)`.
- URL cÃ³ token/query nháº¡y cáº£m; redact khi lÆ°u/log/provenance.
- Nguá»“n cÃ³ prompt injection hoáº·c claim khÃ´ng kiá»ƒm chá»©ng; sanitize thÃ nh evidence, khÃ´ng truyá»n nguyÃªn vÄƒn vÃ o instruction cá»§a model.
- Nhiá»u variant cÃ¹ng sá»­a má»™t content spine; dÃ¹ng revision/fingerprint vÃ  Ä‘Ã¡nh dáº¥u output stale khi nguá»“n Ä‘á»•i.
- Handoff thÃ nh cÃ´ng má»™t pháº§n; ghi target project ID vÃ  cho phÃ©p resume, khÃ´ng táº¡o project trÃ¹ng.
- UI Ä‘Ã³ng tab khi job cháº¡y; polling theo tráº¡ng thÃ¡i + restore theo job ID.

## Blueprint triá»ƒn khai

1. Chá»‘t source types vÃ  giá»›i háº¡n upload/duration; chá»‘t RSS + direct audio hay chá»‰ upload cho MVP.
2. Táº¡o schema union cho create request vÃ  output; giá»¯ source refs/provenance báº¯t buá»™c.
3. Táº¡o service adapter podcast dÃ¹ng STT hiá»‡n cÃ³; khÃ´ng gá»i `/transcribe` qua HTTP ná»™i bá»™ náº¿u cÃ³ thá»ƒ gá»i service trá»±c tiáº¿p.
4. Táº¡o generator profiles cho `story_angles` vÃ  `lesson_story`, tÃ¡i sá»­ dá»¥ng content profile/AI planning.
5. Táº¡o route `/content-tools` vá»›i create/get/list/generate/retry/cancel/handoff; cháº¡y tÃ¡c vá»¥ náº·ng trong worker/thread pool giá»‘ng research/video-inspiration.
6. Táº¡o `ContentToolsPage` vÃ  cÃ¡c panel source/profile/output; thÃªm route vÃ o TanStack tree vÃ  `isWideWorkspace`.
7. Handoff output qua source blocks/timeline beat hiá»‡n cÃ³; quality gate kiá»ƒm tra rights, provenance, duration vÃ  prompt completeness.
8. ThÃªm tests schema, state transition, idempotency, podcast parsing, audio validation, generator output vÃ  handoff.

## Acceptance criteria

- Má»Ÿ `/content-tools` tháº¥y ba tool vÃ  cÃ³ thá»ƒ deep-link báº±ng `?kind=`.
- Podcast nháº­n Ã­t nháº¥t má»™t input Ä‘Æ°á»£c chá»‘t (MVP: audio upload hoáº·c direct audio URL), táº¡o transcript cÃ³ timestamp vÃ  tráº£ vá» prompt pack.
- Má»™t ná»™i dung táº¡o Ä‘Æ°á»£c tá»‘i thiá»ƒu ba gÃ³c ká»ƒ; má»—i gÃ³c giá»¯ source refs vÃ  nÃªu Ä‘iá»ƒm khÃ¡c biá»‡t.
- Má»™t bÃ i há»c táº¡o Ä‘Æ°á»£c story beats, learning objective vÃ  prompt theo scene.
- Job reload/polling khÃ´ng máº¥t tráº¡ng thÃ¡i; retry khÃ´ng táº¡o duplicate output.
- Input lá»—i tráº£ mÃ£ lá»—i á»•n Ä‘á»‹nh, hiá»ƒn thá»‹ gáº§n trÆ°á»ng nháº­p; khÃ´ng ghi lá»™ token/query nháº¡y cáº£m.
- Handoff yÃªu cáº§u rights attestation vÃ  táº¡o tá»‘i Ä‘a má»™t AI Video project cho má»™t idempotency key.
- Typecheck frontend, test backend má»¥c tiÃªu vÃ  full test suite Ä‘áº¡t.

## Khuyáº¿n nghá»‹ cuá»‘i

Chá»n PhÆ°Æ¡ng Ã¡n A. LÃ m MVP theo thá»© tá»±: (1) `story_angles` vÃ  `lesson_story` trÃªn text Ä‘Ã£ cÃ³ vÃ¬ Ã­t rá»§i ro; (2) podcast upload audio; (3) RSS/direct audio URL sau khi cÃ³ resolver vÃ  quota. Chá»‰ táº¡o AI Video project sau bÆ°á»›c review, Ä‘á»ƒ ngÆ°á»i dÃ¹ng kiá»ƒm tra transcript, source refs, claim vÃ  quyá»n sá»­ dá»¥ng.

## TÃ i liá»‡u tham kháº£o

- RSS 2.0 Specification: https://www.rssboard.org/rss-specification
- FastAPI Request Files: https://fastapi.tiangolo.com/tutorial/request-files/
- TanStack Router route trees: https://tanstack.com/router/latest/docs/framework/react/guide/route-trees
- Repository contracts: `backend/routes/research.py`, `backend/routes/video_inspiration.py`, `backend/routes/transcription.py`, `backend/services/video_inspiration.py`, `app/src/router.tsx`
