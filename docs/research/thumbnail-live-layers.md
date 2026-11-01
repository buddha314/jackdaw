# Empty prefab thumbnails with asynchronously placed native LOD meshes

## Reproduction

Jackdaw 0.20.1-rc.1, supported dev/0.20 at 3ca936de, Linux. Open a Project
browser folder containing glTF-backed prefabs with imported native model LODs.
The reeds and scrub-oak fixtures reproduce this: all ten browser tiles get empty
background pictures instead of their models. Files and prefab model paths exist.
The saved scene need not place those prefabs; thumbnail generation is separate.

## Cause

The thumbnail stage uses its own RenderLayers camera and assigns that layer to
the subject hierarchy once during Stage::Spawned. Jackdaw's existing native live
LOD pipeline may replace coarse parts or instantiate descendants afterward. Those
new mesh entities have the default world layer: Bevy does not inherit RenderLayers.
The thumbnail camera therefore misses them. A background-only capture is accepted
as Ready and cached by source path/mtime, surviving editor restarts.

This is editor thumbnail lifecycle handling, not missing model files, gameplay
visibility, broken prefab resolution, or a reason to replace native LOD machinery.

## Fix

Keep descendants of the active ThumbnailSubject on the thumbnail layer, including
late-arriving meshes. Synchronize after native LOD placement / CalculateBounds and
before CheckVisibility; insert only when the layer differs. Continue using the
existing model loader, native LOD selection, camera, framing and screenshot pipeline.
Version thumbnail cache filenames as v2 so old background-only results regenerate.
There are no model, prefab, scene, LOD-policy or game-specific editor changes.

## Focused evidence (2026-11-01)

- One regression passed: descendants added after initial framing receive the
  thumbnail layer, including grandchildren; the cache key invalidates old results.
- Editor executable build passed. No broad suite.
- Independent 20-second, 60 Hz baseline: four reed and six scrub-oak previews were
  all 681-byte PNGs containing exactly one RGB colour.
- Independent 20-second fixed review on a separate endpoint, asserting project and
  executable identity before operators: all ten generated nonuniform previews.
  Reeds contain 646–752 RGB colours; dormant oaks contain 493–602. The gallery
  screenshot visibly shows both families. The watchdog ended the run at 20 seconds.
- Two attempted fixed captures using a busy shared diagnostic endpoint were
  invalid and excluded. One reached another editor's art project; only panel
  navigation and an ignored screenshot were requested there, with no scene or
  asset file edits. The successful comparison used a separate port and explicit
  project/executable checks. Keep diagnostic endpoints isolated from other agents.

Local evidence: /tmp/flora-thumbnail-before-after.json and
/tmp/jackdaw-flicker-flora-thumbnail-isolated-fixed.log.
