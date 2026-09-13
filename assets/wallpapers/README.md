# Seasonal photography

These four photographs are bundled for offline use in ShadowPlay Notifier.
They were downloaded from [Unsplash](https://unsplash.com/) and remain under the
[Unsplash License](https://unsplash.com/license), separate from the application's
MIT license. No photo search, account, API key, or wallpaper download occurs at
runtime.

Each file is centre-cropped to 16:9 and stored as JPEG at 1280x720. The app
crops further to the display's own aspect ratio, composes the background at
480x320, and then scales it up, so it never reads more than about 764x320 from
these files. Anything larger would only grow the executable.

| File | Season | Photographer | Subject |
| --- | --- | --- | --- |
| spring.jpg | March to May | Arno Smit | Cherry blossom branches |
| summer.jpg | June to August | Alexander Mils | Palm trees along a calm sea |
| autumn.jpg | September to November | Alisa Anton | Cocoa and an open book on a blanket |
| winter.jpg | December to February | Aaron Burden | A frozen bubble covered in frost |

The Unsplash License does not require attribution, but the photographers are
credited here. Search a photographer's name on Unsplash to find the original
photograph.

To swap a photo, drop a replacement into this folder under the same base name.
`component/sky.py` accepts `.png`, `.jpg`, and `.jpeg`, in that order, and
`ShadowPlayNotifier.spec` bundles whichever one it finds first.
