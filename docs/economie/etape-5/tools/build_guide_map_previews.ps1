$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationCore
$guideProject = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..'))
$guideAssets = Join-Path $guideProject 'renblood-website/renblood-website/public/accueil'
$mapPath = Join-Path $guideAssets 'carte-renblood.png'
$mapFrame = [System.Windows.Media.Imaging.BitmapFrame]::Create([Uri]::new($mapPath), [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat, [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad)
foreach ($mapWidth in (@(640, $mapFrame.PixelWidth) | Sort-Object -Unique)) {
    if ($mapWidth -gt $mapFrame.PixelWidth) { continue }
    $mapScale = [double]$mapWidth / $mapFrame.PixelWidth
    $mapPreview = [System.Windows.Media.Imaging.TransformedBitmap]::new($mapFrame, [System.Windows.Media.ScaleTransform]::new($mapScale, $mapScale))
    $mapEncoder = [System.Windows.Media.Imaging.JpegBitmapEncoder]::new()
    $mapEncoder.QualityLevel = 88
    $mapEncoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($mapPreview))
    $mapOutput = Join-Path $guideAssets "carte-renblood-$mapWidth.jpg"
    $mapStream = [IO.File]::Open($mapOutput, [IO.FileMode]::Create)
    try { $mapEncoder.Save($mapStream) } finally { $mapStream.Dispose() }
    $mapFile = Get-Item -LiteralPath $mapOutput
    Write-Output "$($mapFile.Name): $($mapFile.Length) bytes"
}
