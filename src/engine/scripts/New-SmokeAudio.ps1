# Generate non-patient development speech entirely with the installed Windows voice.
# Run from any directory; writes the ignored engine/sample.wav development fixture.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$outputDirectory = Split-Path -Parent $PSScriptRoot
$outputPath = Join-Path $outputDirectory 'sample.wav'
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.SelectVoice('Microsoft David Desktop')
    $synth.SetOutputToWaveFile($outputPath)
    $synth.Speak('The rabbit sits in the sun.')
} finally {
    $synth.Dispose()
}
Write-Output $outputPath
