# RNN Models for Audio Denoising

This directory contains neural network models (`.rnnn` files) for FFmpeg's `arnndn` filter, which provides AI-based audio noise reduction.

## Available Models

### std.rnnn (Standard Model) - **Recommended**
- **Purpose**: General-purpose noise reduction
- **Best for**: Most common use cases, speech with background noise
- **Download**: Automatic (required)
- **Usage**: Default model used by AI presets (`tv_ai_speech`, `web_ai_speech`)

### bd.rnnn (Balloon/Directional Noise Model) - **Optional**
- **Purpose**: Specialized for wind noise and directional interference
- **Best for**: Outdoor recordings, windy conditions, directional noise sources
- **Download**: Automatic (optional)
- **Usage**: Can be specified manually in preset configuration

### lq.rnnn (Low Quality Model) - **Optional**
- **Purpose**: Optimized for heavily degraded audio sources
- **Best for**: Old recordings, low bitrate audio, heavily compressed sources
- **Download**: Automatic (optional)
- **Usage**: Can be specified manually in preset configuration

## Automatic Installation

Models are automatically downloaded during:
- **Initial installation** (`install.sh`)
- **Project updates** (`update.sh`)
- **Container startup** (`entrypoint.production.sh`)

The script `download_models.sh` downloads models from public GitHub repositories:
- Primary source: `github.com/GregorR/rnnoise-models`
- Models are stored in this directory (`tools/rnn_models/`)

## Manual Installation

If automatic download fails, you can download models manually:

```bash
# Standard model (required for AI presets)
curl -L -o std.rnnn https://github.com/GregorR/rnnoise-models/raw/master/std.rnnn

# Optional models
curl -L -o bd.rnnn https://github.com/GregorR/rnnoise-models/raw/master/bd.rnnn
curl -L -o lq.rnnn https://github.com/GregorR/rnnoise-models/raw/master/lq.rnnn
```

## Configuration

By default, the system uses `std.rnnn` from this directory. To use a different model:

1. **Via ToolsConfig** (Admin → Tools → Tools Config):
   - Set `ARNNDN Model Path` to full path of desired model (e.g., `/app/tools/rnn_models/bd.rnnn`)

2. **Via Environment Variable**:
   - Set `TOOLS_ARNNDN_MODEL_PATH=/path/to/model.rnnn` in `.env` file

3. **Via Preset Configuration**:
   - Edit `tools/services/audio_presets.json`
   - Add `"arnndn_model": "/path/to/model.rnnn"` in preset filters

## Model Selection Guide

| Scenario | Recommended Model | Reason |
|----------|------------------|--------|
| General speech with background noise | `std.rnnn` | Best balance for most cases |
| Outdoor/windy recordings | `bd.rnnn` | Optimized for wind noise |
| Old/degraded audio | `lq.rnnn` | Better for low quality sources |
| Studio-quality recordings | `std.rnnn` | Standard model sufficient |
| Interviews/monologues | `std.rnnn` | General purpose works well |

## Technical Details

- **Model Format**: `.rnnn` (RNN model binary format)
- **Filter**: FFmpeg `arnndn` (Audio Recurrent Neural Network Denoise)
- **Size**: ~100-200 KB per model
- **License**: Models are open source and freely available

## Troubleshooting

**Models not downloading automatically:**
- Check internet connectivity in container
- Verify GitHub repository is accessible
- Check container logs for download errors
- Download manually using commands above

**AI presets not working:**
- Ensure `std.rnnn` exists in this directory
- Check `ToolsConfig.arnndn_model_path` is empty or points to valid model
- Verify FFmpeg version supports `arnndn` filter (FFmpeg 4.0+)

**Want to use different model:**
- Download desired model manually
- Configure path in ToolsConfig or environment variable
- Or modify preset JSON to specify model path
