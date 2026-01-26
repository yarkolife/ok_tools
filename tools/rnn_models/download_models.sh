#!/bin/bash
# Download RNN models for FFmpeg arnndn filter
# This script downloads standard models from public repositories
# Non-critical: script continues even if download fails

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$SCRIPT_DIR"
TEMP_DIR=$(mktemp -d)

# Cleanup on exit
trap "rm -rf $TEMP_DIR" EXIT

echo "Downloading RNN models for arnndn filter..."

# Download from archived repository
# Primary source: github.com/richardpl/arnndn-models (archived, but still accessible)

# Standard model (std.rnnn) - most commonly used
STD_MODEL_URL="https://github.com/richardpl/arnndn-models/raw/master/std.rnnn"
STD_MODEL_PATH="$MODELS_DIR/std.rnnn"

if [ ! -f "$STD_MODEL_PATH" ]; then
    echo "  Downloading std.rnnn (standard model)..."
    if curl -L -f -o "$STD_MODEL_PATH" "$STD_MODEL_URL" 2>/dev/null; then
        echo "  ✓ Downloaded std.rnnn"
    else
        echo "  ⚠️  Warning: Could not download std.rnnn automatically"
        echo "     You can download it manually from:"
        echo "     https://github.com/richardpl/arnndn-models"
        rm -f "$STD_MODEL_PATH"
    fi
else
    echo "  ✓ std.rnnn already exists"
fi

# Optional: Download additional models
# Model descriptions:
# - std.rnnn: Standard model (general purpose, recommended for most cases)
# - bd.rnnn: Balloon/directional noise model (better for wind noise, directional interference)
# - lq.rnnn: Low quality audio model (for heavily degraded audio sources)

# Balloon/directional noise model (bd.rnnn) - useful for wind noise and directional interference
BD_MODEL_URL="https://github.com/richardpl/arnndn-models/raw/master/bd.rnnn"
BD_MODEL_PATH="$MODELS_DIR/bd.rnnn"

if [ ! -f "$BD_MODEL_PATH" ]; then
    echo "  Downloading bd.rnnn (balloon/directional noise model)..."
    if curl -L -f -o "$BD_MODEL_PATH" "$BD_MODEL_URL" 2>/dev/null; then
        echo "  ✓ Downloaded bd.rnnn"
    else
        echo "  ⚠️  Could not download bd.rnnn (optional, skipping)"
        rm -f "$BD_MODEL_PATH"
    fi
else
    echo "  ✓ bd.rnnn already exists"
fi

# Low quality model (lq.rnnn) - for heavily degraded audio
LQ_MODEL_URL="https://github.com/richardpl/arnndn-models/raw/master/lq.rnnn"
LQ_MODEL_PATH="$MODELS_DIR/lq.rnnn"

if [ ! -f "$LQ_MODEL_PATH" ]; then
    echo "  Downloading lq.rnnn (low quality audio model)..."
    if curl -L -f -o "$LQ_MODEL_PATH" "$LQ_MODEL_URL" 2>/dev/null; then
        echo "  ✓ Downloaded lq.rnnn"
    else
        echo "  ⚠️  Could not download lq.rnnn (optional, skipping)"
        rm -f "$LQ_MODEL_PATH"
    fi
else
    echo "  ✓ lq.rnnn already exists"
fi

echo ""
echo "RNN models download complete!"
echo "Models location: $MODELS_DIR"
if [ -f "$STD_MODEL_PATH" ]; then
    echo "  ✓ std.rnnn available (standard, general purpose)"
    ls -lh "$STD_MODEL_PATH"
fi
if [ -f "$BD_MODEL_PATH" ]; then
    echo "  ✓ bd.rnnn available (balloon/directional noise)"
    ls -lh "$BD_MODEL_PATH"
fi
if [ -f "$LQ_MODEL_PATH" ]; then
    echo "  ✓ lq.rnnn available (low quality audio)"
    ls -lh "$LQ_MODEL_PATH"
fi
