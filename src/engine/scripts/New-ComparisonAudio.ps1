# Generate adult synthetic comparison fixtures, not simulated clinical child data.
# Re-run from any directory. Outputs are ignored under examples/synthetic-soa/.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$comparisonDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'examples\synthetic-soa'
New-Item -ItemType Directory -Path $comparisonDirectory -Force | Out-Null
$uh = [string][char]0x028C
$eh = [string][char]0x025B
$seatGroups = @(@{ label = 'seat'; start = 0; end = 3 })
$sunsetGroups = @(@{ label = 'sun'; start = 0; end = 3 }, @{ label = 'set'; start = 3; end = 6 })
$fixtures = @(
    @{ id = 'seat-control'; label = 'Seat - control'; spoken_text = 'Seat.'; target_word = 'seat'; expected_phones = @('s','i','t'); intended_change = 'none'; syllables = $seatGroups },
    @{ id = 'seat-substitution'; label = 'Seat - substitution'; spoken_text = 'Sheet.'; target_word = 'seat'; expected_phones = @('s','i','t'); intended_change = 's to sh'; syllables = $seatGroups },
    @{ id = 'seat-omission'; label = 'Seat - omission'; spoken_text = 'See.'; target_word = 'seat'; expected_phones = @('s','i','t'); intended_change = 'omit final t'; syllables = $seatGroups },
    @{ id = 'seat-addition'; label = 'Seat - addition'; spoken_text = 'Seats.'; target_word = 'seat'; expected_phones = @('s','i','t'); intended_change = 'add final s'; syllables = $seatGroups },
    @{ id = 'sunset-control'; label = 'Sunset - control'; spoken_text = 'Sunset.'; target_word = 'sunset'; expected_phones = @('s',$uh,'n','s',$eh,'t'); intended_change = 'none'; syllables = $sunsetGroups },
    @{ id = 'sunset-substitution'; label = 'Sunset - second vowel'; spoken_text = 'Sun sat.'; target_word = 'sunset'; expected_phones = @('s',$uh,'n','s',$eh,'t'); intended_change = 'second vowel eh to ae'; syllables = $sunsetGroups }
)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.SelectVoice('Microsoft David Desktop')
    $synth.Rate = -1
    foreach ($fixture in $fixtures) {
        $fixture.audio_file = $fixture.id + '.wav'
        $synth.SetOutputToWaveFile((Join-Path $comparisonDirectory $fixture.audio_file))
        $synth.Speak($fixture.spoken_text)
        $synth.SetOutputToNull()
    }
} finally { $synth.Dispose() }
$manifest = @{ voice = 'Microsoft David Desktop'; note = 'Synthetic adult speech. Intended changes are prompts, not verified model results.'; fixtures = $fixtures }
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $comparisonDirectory 'manifest.json') -Encoding UTF8
Write-Output ('Generated ' + $fixtures.Count + ' WAV files and manifest.json in ' + $comparisonDirectory)
