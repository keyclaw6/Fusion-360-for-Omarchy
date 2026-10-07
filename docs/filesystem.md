# Local files and folders

Use **File → Export → Autodesk Fusion Archive (`.f3d`) → …** to choose a
local location. The first **Save** in the file chooser selects the path; the
following **Export** creates the archive. Fusion's ordinary Save and Save
Component Copy As store designs in Autodesk projects, as on Windows/macOS.

The installed mappings expose `X:\` as your home and `Z:\` as the filesystem.
In the file chooser, expand **My Computer** to browse those drives, or enter
a complete path in **File name**, for example
`Z:\home\YOUR_USER\Downloads\part.f3d`. Choose any directory your Linux
user can write to, including mounted storage. Linux permissions still apply.

To use host Documents/Downloads instead of the private Windows profile folders,
and reset the Qt file chooser's remembered starting folder to your home, run
this once while Fusion is open:

```sh
fusion360-for-omarchy configure-folders
```

This reads XDG user directory locations, edits only the installation's Windows
shell-folder and Qt file-dialog preferences through Wine's registry API, and
exports the three previous preference keys under the private state directory's
`host-folders/` first. It moves no documents. Close and reopen Fusion to refresh
cached shell folder locations. The saved `.reg` files can be imported with this
installation's `reg.exe` if those preferences need to be restored.

On 7 October 2026, Fusion 2705.1.30's native Export UI produced valid `.f3d` archives in the
actual host Downloads and Home directories. The paths were selected in Export
and both resulting archives were independently checked for ZIP CRC and metadata;
only those uniquely named test files were then deleted. This is local export access,
not a replacement of Autodesk's cloud Save feature.
