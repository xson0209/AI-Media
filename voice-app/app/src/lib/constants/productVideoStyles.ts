/**
 * Style presets for the product-video prompt flow.
 *
 * These fill the free-text `visual_style` field — they are a shortcut, not a
 * constraint. The user can edit any preset text, and picking one then editing
 * flips `visual_style_preset` to `custom`.
 *
 * Two rules every preset must follow (asserted in
 * backend/tests/test_product_video.py):
 *   1. Describe at least one motion source. A preset must never produce a
 *      static shot — the video is dead the moment nothing moves.
 *   2. Say nothing that fights the fixed `Product fidelity` section the prompt
 *      builder appends. Presets describe look and motion; label fidelity is
 *      enforced separately and unconditionally.
 *
 * The first three presets are modelled on real Veo output that was analysed
 * frame by frame — see docs/research/ai-video-perf-va-mo-rong-content-types.md
 * section 2. The rest are extrapolations and should be revised once we have
 * real output to compare against.
 */

export type ProductVideoStylePreset = {
  value: string;
  /** Vietnamese label shown in the dropdown. */
  label: string;
  /** English text written into the visual_style textarea. */
  text: string;
};

export const PRODUCT_VIDEO_STYLE_PRESETS: ProductVideoStylePreset[] = [
  {
    value: 'ugc_street',
    label: 'UGC cầm sản phẩm ngoài đường',
    text: [
      'Handheld vertical UGC look, shot on a phone, single continuous take.',
      'A hand raises the product into frame at chest height and holds it steady with the front label square to camera.',
      'Camera: handheld with slight natural shake, a small drift to keep the product centered, no zoom.',
      'Environment: a busy street in late afternoon — passing motorbikes, a vendor moving in the middle distance, foot traffic. Background is softly out of focus and clearly in motion while the product stays sharp.',
      'Lighting: warm natural daylight, soft shadow, no harsh glare across the label surface.',
    ].join('\n'),
  },
  {
    value: 'studio_beauty',
    label: 'Beauty shot studio, camera orbit chậm',
    text: [
      'Vertical studio beauty shot, single continuous take, nothing enters or leaves frame.',
      'The product rests centered on a dark surface. Only the camera moves.',
      'Camera: slow continuous orbit of roughly 40 degrees at a low three-quarter angle, constant speed, ending with the front face toward camera. Shallow depth of field, product fully in focus throughout.',
      'Environment: colored accent lighting drifting slowly behind and along the surface edge, faint moving reflection on the tabletop, dark falloff background.',
      'Lighting: soft key from upper left so material texture stays readable, colored rim light separating the product from the background, no blown highlights.',
    ].join('\n'),
  },
  {
    value: 'presenter_ad',
    label: 'Người thật thuyết trình quảng cáo',
    text: [
      'Vertical direct-to-camera advertising shot, one presenter, single continuous take.',
      'A presenter holds the product up beside their face, front label toward camera, and speaks to the viewer.',
      'Camera: slow push-in from medium to medium-close, steady, no cut.',
      'Environment: a real workplace behind the presenter — shelving, equipment, a colleague passing far in the background. Keep the background alive but not distracting.',
      'Lighting: soft frontal key, gentle fill, natural skin tone, no hotspot on the packaging.',
    ].join('\n'),
  },
  {
    value: 'macro_closeup',
    label: 'Cận cảnh chi tiết sản phẩm',
    text: [
      'Vertical macro detail shot, single continuous take, extreme close range.',
      'Frame one specific feature of the product — a seam, a port, a texture, a closure — large in frame.',
      'Camera: slow lateral slide across the detail, or a slow rack focus from the detail to the label and back. Very shallow depth of field.',
      'Environment: slow-moving specular highlight travelling across the surface as the camera slides, faint dust or fabric motion at the edge of frame.',
      'Lighting: hard raking side light to bring out relief and texture, deep shadow on the opposite side.',
    ].join('\n'),
  },
  {
    value: 'unboxing',
    label: 'Unboxing trên bàn',
    text: [
      'Vertical unboxing shot from a high front angle, single continuous take.',
      'Two hands open the packaging and lift the product out, then turn the front label toward camera and hold it there.',
      'Camera: locked high angle with a slow push-in as the product is revealed, no cut.',
      'Environment: hands and packaging in constant motion, tissue or wrapping shifting, discarded lid moving out of frame.',
      'Lighting: bright even overhead light, soft shadow under the hands, no glare on the packaging film.',
    ].join('\n'),
  },
  {
    value: 'flatlay',
    label: 'Flatlay nhìn từ trên xuống',
    text: [
      'Vertical top-down flatlay, single continuous take.',
      'The product sits centered among a small number of related props, front label facing straight up to camera.',
      'Camera: slow top-down descent toward the product, or a slow rotation of the whole arrangement around the product as its still center.',
      'Environment: props sliding gently into place around the product, a hand entering frame to adjust one prop, fabric or leaves shifting.',
      'Lighting: large soft overhead source, clean even exposure, shadows short and directional.',
    ].join('\n'),
  },
  {
    value: 'custom',
    label: 'Tự nhập',
    text: '',
  },
];

export const PRODUCT_VIDEO_STYLE_CUSTOM = 'custom';

export function productVideoStylePreset(value: string | null | undefined) {
  return PRODUCT_VIDEO_STYLE_PRESETS.find((preset) => preset.value === value);
}
