"""Video generator service for slideshow creation."""

import os
import random
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Callable

from django.conf import settings
from django.core.exceptions import ValidationError

from tools.models import SlideshowProject, SlideshowMedia, SlideshowAudio, ToolsConfig


class VideoGeneratorError(Exception):
    """Exception raised by VideoGenerator."""
    pass


class VideoGenerator:
    """Service class for generating video slideshows from images and videos."""
    
    # Transition pool for random selection
    TRANSITIONS_POOL = [
        "fade", "fadeblack", "fadewhite",
        "wipeleft", "wiperight", "wipeup", "wipedown",
        "slideleft", "slideright", "slideup", "slidedown",
        "smoothleft", "smoothright",
        "circleopen", "circleclose", "radial"
    ]
    
    def __init__(self, project: SlideshowProject):
        """Initialize video generator with project settings."""
        self.project = project
        self.config = ToolsConfig.get_config()
        self.ffmpeg = getattr(settings, 'TOOLS_FFMPEG_PATH', self.config.ffmpeg_path)
        self.ffprobe = getattr(settings, 'TOOLS_FFPROBE_PATH', self.config.ffprobe_path)
        
        # Load project settings
        self.slide_sec = self.project.slide_duration
        self.fps = self.project.fps
        self.width = self.project.width
        self.height = self.project.height
        self.use_transitions = self.project.use_transitions
        self.transition = self.project.transition_type
        self.trans_dur = self.project.transition_duration
        self.video_bitrate = self.project.video_bitrate
        self.audio_bitrate = self.project.audio_bitrate
        self.video_codec = self.project.video_codec or self.get_optimal_codec()
        
        # GOP settings (frames per keyframe)
        self.gop = 75
        
    @staticmethod
    def is_image(file_path: Path) -> bool:
        """Check if file is an image."""
        return file_path.suffix.lower() in (".jpg", ".jpeg", ".png")
    
    @staticmethod
    def is_video(file_path: Path) -> bool:
        """Check if file is a video."""
        return file_path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v")
    
    def get_audio_duration(self, file_path: Path) -> float:
        """Get duration of audio file in seconds."""
        try:
            p = subprocess.run(
                [self.ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nk=1:nw=1", str(file_path)],
                capture_output=True, text=True, check=True, timeout=30
            )
            return float(p.stdout.strip())
        except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired) as e:
            raise VideoGeneratorError(f"Failed to get audio duration: {e}")
    
    def get_video_duration(self, file_path: Path) -> float:
        """Get duration of video file in seconds."""
        try:
            p = subprocess.run(
                [self.ffprobe, "-v", "error", "-show_entries", "stream=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
                capture_output=True, text=True, check=True, timeout=30
            )
            # May have multiple lines (video+audio), take first
            durations = [float(d.strip()) for d in p.stdout.strip().split('\n') 
                        if d.strip() and d.strip() != 'N/A']
            return durations[0] if durations else 0.0
        except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired) as e:
            raise VideoGeneratorError(f"Failed to get video duration: {e}")
    
    def ff_safe(self, path: Path) -> str:
        """Safely escape path for concat list."""
        return str(path).replace("'", r"'\''")
    
    def compute_tail_for_xfade(self, num_images: int, audio_len: float) -> float:
        """
        Calculate how much to add to last slide to match audio length.
        
        Base length of xfade chain with N slides:
        base = N*SLIDE_SEC - (N-1)*TRANS_DUR
        Return how much to add to last slide to make video >= audio.
        """
        if num_images <= 0:
            return 0.0
        base = num_images * self.slide_sec - (num_images - 1) * self.trans_dur
        tail = max(0.0, audio_len - base)
        return round(tail, 3)
    
    def get_optimal_codec(self) -> str:
        """Detect optimal video codec (hardware acceleration if available and working)."""
        # Always use libx264 as default - hardware encoders require specific drivers
        # that may not be available in Docker containers
        return "libx264"
        
        # Note: Hardware encoder detection disabled due to Docker environment limitations
        # Hardware encoders (h264_nvenc, h264_qsv, h264_amf) require:
        # - NVIDIA drivers and CUDA for nvenc
        # - Intel Quick Sync for qsv  
        # - AMD drivers for amf
        # These are typically not available in standard Docker containers
    
    def video_encoder_args(self, codec: str) -> List[str]:
        """Get video encoder arguments for specified codec."""
        bufsize = "10M"
        common = [
            "-b:v", self.video_bitrate, "-maxrate", self.video_bitrate, "-bufsize", bufsize,
            "-g", str(self.gop),
            "-bf", "0",  # No B-frames
            "-pix_fmt", "yuv420p",  # 4:2:0
            "-profile:v", "high", "-level:v", "4.1",
        ]
        color = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
        
        if codec == "h264_nvenc":
            return ["-c:v", "h264_nvenc", "-rc", "cbr", "-preset", "p5", *common, *color]
        
        if codec == "h264_qsv":
            return ["-c:v", "h264_qsv", "-look_ahead", "0", *common, *color]
        
        if codec == "h264_amf":
            return ["-c:v", "h264_amf", "-quality", "quality", *common, *color]
        
        # libx264 - strict CBR, no B-frames, fixed GOP
        return [
            "-c:v", "libx264", "-preset", "veryfast",
            *common,
            "-keyint_min", str(self.gop), "-sc_threshold", "0",
            "-x264-params", "nal-hrd=cbr:vbv-bufsize=10000:vbv-maxrate=5000:scenecut=0:force-cfr=1:bframes=0",
            *color
        ]
    
    def validate_media(self) -> bool:
        """Validate that all required media files exist."""
        media_files = list(self.project.media_files.all().order_by('order'))
        if not media_files:
            raise VideoGeneratorError("No media files found in project")
        
        audio_files = list(self.project.audio_files.all())
        if not audio_files:
            raise VideoGeneratorError("No audio file found in project")
        
        # Check all files exist - handle mounted paths
        storage_path = self.config.get_effective_storage_path()
        for media in media_files:
            # Try to resolve file path - check if it's in mounted storage
            if storage_path:
                # Check if file exists in mounted path
                storage_base = Path(storage_path)
                rel_path = media.file.name
                mounted_path = storage_base / rel_path
                if mounted_path.exists():
                    continue
            # Fallback to default path
            try:
                if os.path.exists(media.file.path):
                    continue
            except (ValueError, AttributeError):
                pass
            raise VideoGeneratorError(f"Media file not found: {media.file.name}")
        
        for audio in audio_files:
            # Try to resolve file path - check if it's in mounted storage
            if storage_path:
                # Check if file exists in mounted path
                storage_base = Path(storage_path)
                rel_path = audio.file.name
                mounted_path = storage_base / rel_path
                if mounted_path.exists():
                    continue
            # Fallback to default path
            try:
                if os.path.exists(audio.file.path):
                    continue
            except (ValueError, AttributeError):
                pass
            raise VideoGeneratorError(f"Audio file not found: {audio.file.name}")
        
        # Check ffmpeg/ffprobe
        try:
            subprocess.run([self.ffmpeg, "-version"], capture_output=True, check=True, timeout=5)
            subprocess.run([self.ffprobe, "-version"], capture_output=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            raise VideoGeneratorError(f"FFmpeg or FFprobe not found or not working")
        
        return True
    
    def prepare_inputs(self) -> tuple[List[Path], Path]:
        """Prepare media and audio file paths, sorted by order."""
        storage_path = self.config.get_effective_storage_path()
        # Get media files ordered by order field (ascending)
        media_files = list(self.project.media_files.all().order_by('order', 'id'))
        
        # Log order for debugging
        import logging
        logger = logging.getLogger('django')
        logger.debug(f"Preparing inputs for project {self.project.id}: {len(media_files)} media files in order: {[f'{m.id}(order={m.order})' for m in media_files]}")
        
        # Resolve media file paths - check mounted storage first
        media_paths = []
        for m in media_files:
            if storage_path:
                # Check if file exists in mounted path
                storage_base = Path(storage_path)
                rel_path = m.file.name
                mounted_path = storage_base / rel_path
                if mounted_path.exists():
                    media_paths.append(mounted_path)
                    continue
            # Fallback to default path
            try:
                media_paths.append(Path(m.file.path))
            except (ValueError, AttributeError):
                raise VideoGeneratorError(f"Media file path not found: {m.file.name}")
        
        audio_files = list(self.project.audio_files.all())
        if not audio_files:
            raise VideoGeneratorError("No audio file found")
        
        # Resolve audio file path - check mounted storage first
        audio = audio_files[0]
        if storage_path:
            # Check if file exists in mounted path
            storage_base = Path(storage_path)
            rel_path = audio.file.name
            mounted_path = storage_base / rel_path
            if mounted_path.exists():
                audio_path = mounted_path
            else:
                try:
                    audio_path = Path(audio.file.path)
                except (ValueError, AttributeError):
                    raise VideoGeneratorError(f"Audio file path not found: {audio.file.name}")
        else:
            try:
                audio_path = Path(audio.file.path)
            except (ValueError, AttributeError):
                raise VideoGeneratorError(f"Audio file path not found: {audio.file.name}")
        
        return media_paths, audio_path
    
    def build_xfade_command(self, media: List[Path], audio: Path, out_path: Path, audio_len: float) -> List[str]:
        """Build FFmpeg command with xfade transitions."""
        if not media:
            raise VideoGeneratorError("No media files provided")
        
        # Calculate how many slides needed to cover audio length
        needed = 1
        covered = self.slide_sec
        step = max(0.01, self.slide_sec - self.trans_dur)
        while covered < audio_len:
            needed += 1
            covered += step
        
        # Extend last slide to match audio exactly
        base_no_tail = needed * self.slide_sec - (needed - 1) * self.trans_dur
        tail = max(0.0, audio_len - base_no_tail)
        
        # Create cyclic sequence of media files
        seq_media = [media[i % len(media)] for i in range(needed)]
        
        # Build input arguments
        inputs = []
        for i, item in enumerate(seq_media):
            dur = self.slide_sec + (tail if i == len(seq_media) - 1 else 0.0)
            if self.is_image(item):
                inputs += ["-loop", "1", "-t", str(dur), "-i", str(item)]
            else:
                inputs += ["-t", str(dur), "-i", str(item)]
        
        # Build filter complex for xfade
        vf_base = (
            f"settb=expr=1/{self.fps},fps={self.fps},"
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"format=yuv420p,setsar=1"
        )
        
        chains = [f"[{i}:v]{vf_base}[v{i}]" for i in range(len(seq_media))]
        last = "[v0]"
        offset = self.slide_sec - self.trans_dur
        for i in range(1, len(seq_media)):
            tname = random.choice(self.TRANSITIONS_POOL) if self.transition == "random" else self.transition
            chains.append(f"{last}[v{i}]xfade=transition={tname}:duration={self.trans_dur}:offset={offset}[x{i}]")
            last = f"[x{i}]"
            offset += self.slide_sec - self.trans_dur
        
        fcomplex = ";".join(chains)
        
        # Audio input index comes after all video inputs
        audio_input_index = len(seq_media)
        vargs = self.video_encoder_args(self.video_codec)
        
        # Check if output is in mounted storage (network path)
        # Don't use +faststart for network paths as it requires file rewrite at the end
        # which can cause issues with NFS/CIFS
        output_path_config = self.config.get_effective_output_path()
        is_mounted_path = output_path_config and str(out_path).startswith(str(Path(output_path_config).resolve()))
        
        cmd = [
            self.ffmpeg, "-y",
            *inputs,
            "-i", str(audio),
            "-filter_complex", fcomplex,
            "-map", last, "-map", f"{audio_input_index}:a:0",
            "-fps_mode", "cfr", "-r", str(self.fps),
            *vargs,
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", self.audio_bitrate,
        ]
        
        # Only use faststart for local paths (not mounted network storage)
        if not is_mounted_path:
            cmd.append("-movflags")
            cmd.append("+faststart")
        
        cmd.extend([
            "-video_track_timescale", "25000",
            "-shortest",
            str(out_path)
        ])
        return cmd
    
    def build_simple_command(self, media: List[Path], audio: Path, out_path: Path, audio_len: float) -> List[str]:
        """Build simple concat command without transitions."""
        # Create concat file
        concat_file = out_path.parent / "concat_list.txt"
        full = int(audio_len // self.slide_sec)
        rem = round(audio_len - full * self.slide_sec, 1)
        if full == 0:
            rem = max(int(audio_len), 1)
        
        with open(concat_file, "w", encoding="utf-8") as f:
            idx = 0
            for _ in range(full):
                item = media[idx % len(media)]
                f.write(f"file '{self.ff_safe(item)}'\n")
                if self.is_video(item):
                    f.write(f"inpoint 0\n")
                    f.write(f"outpoint {self.slide_sec}\n")
                f.write(f"duration {self.slide_sec}\n")
                idx += 1
            
            if rem > 0:
                last = media[idx % len(media)]
                f.write(f"file '{self.ff_safe(last)}'\n")
                if self.is_video(last):
                    f.write(f"inpoint 0\n")
                    f.write(f"outpoint {rem}\n")
                f.write(f"duration {rem}\n")
                f.write(f"file '{self.ff_safe(last)}'\n")
            elif full > 0:
                last = media[(idx-1) % len(media)]
                f.write(f"file '{self.ff_safe(last)}'\n")
        
        vf = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"format=yuv420p,setsar=1"
        )
        
        vargs = self.video_encoder_args(self.video_codec)
        
        # Check if output is in mounted storage (network path)
        # Don't use +faststart for network paths as it requires file rewrite at the end
        # which can cause issues with NFS/CIFS
        output_path_config = self.config.get_effective_output_path()
        is_mounted_path = output_path_config and str(out_path).startswith(str(Path(output_path_config).resolve()))
        
        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0",
            "-fps_mode", "cfr", "-r", str(self.fps),
            "-vf", vf,
            *vargs,
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", self.audio_bitrate,
        ]
        
        # Only use faststart for local paths (not mounted network storage)
        if not is_mounted_path:
            cmd.append("-movflags")
            cmd.append("+faststart")
        
        cmd.extend([
            "-video_track_timescale", "25000",
            "-shortest",
            str(out_path)
        ])
        return cmd
    
    def generate(self, progress_callback: Optional[Callable[[str], None]] = None) -> Path:
        """
        Generate video slideshow.
        
        Args:
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Path to generated video file
            
        Raises:
            VideoGeneratorError: If generation fails
        """
        # Validate inputs
        self.validate_media()
        
        # Prepare file paths
        media_paths, audio_path = self.prepare_inputs()
        
        # Get audio duration
        audio_len = self.get_audio_duration(audio_path)
        
        # Determine output path - use mounted path from config if available
        output_path_config = self.config.get_effective_output_path()
        if output_path_config:
            # Use mounted output path
            output_base = Path(output_path_config)
            output_dir = output_base / f"tools/slideshow/{self.project.id}/output"
        else:
            # Fallback to MEDIA_ROOT
            output_dir = Path(settings.MEDIA_ROOT) / f"tools/slideshow/{self.project.id}/output"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"{self.project.name.replace(' ', '_')}_{self.project.id}.mp4"
        output_path = output_dir / output_filename
        
        # Build command
        if self.use_transitions:
            cmd = self.build_xfade_command(media_paths, audio_path, output_path, audio_len)
        else:
            cmd = self.build_simple_command(media_paths, audio_path, output_path, audio_len)
        
        # Execute FFmpeg
        if progress_callback:
            progress_callback("Starting video generation...")
        
        # Log command for debugging (without sensitive paths)
        import logging
        logger = logging.getLogger('django')
        logger.debug(f"FFmpeg command: {' '.join(cmd[:10])}... (truncated)")
        
        try:
            # Run with progress output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read stderr for progress (FFmpeg outputs progress to stderr)
            error_lines = []
            for line in process.stderr:
                line = line.strip()
                if progress_callback and ("time=" in line or "frame=" in line):
                    progress_callback(line)
                else:
                    # Collect error/warning lines
                    error_lines.append(line)
            
            process.wait()
            
            if process.returncode != 0:
                error_output = "\n".join(error_lines[-20:]) if error_lines else "Unknown error (no stderr output)"
                
                # If hardware encoder failed, try fallback to libx264
                if self.video_codec in ("h264_nvenc", "h264_qsv", "h264_amf") and "Cannot load" in error_output:
                    logger.warning(f"Hardware encoder {self.video_codec} failed, falling back to libx264")
                    self.video_codec = "libx264"
                    
                    # Rebuild command with libx264
                    if self.use_transitions:
                        cmd = self.build_xfade_command(media_paths, audio_path, output_path, audio_len)
                    else:
                        cmd = self.build_simple_command(media_paths, audio_path, output_path, audio_len)
                    
                    # Retry with libx264
                    logger.debug(f"Retrying with libx264 codec")
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    
                    error_lines = []
                    for line in process.stderr:
                        line = line.strip()
                        if progress_callback and ("time=" in line or "frame=" in line):
                            progress_callback(line)
                        else:
                            error_lines.append(line)
                    
                    process.wait()
                    
                    if process.returncode != 0:
                        error_output = "\n".join(error_lines[-20:]) if error_lines else "Unknown error (no stderr output)"
                        raise VideoGeneratorError(f"FFmpeg failed with return code {process.returncode}:\n{error_output}")
                else:
                    raise VideoGeneratorError(f"FFmpeg failed with return code {process.returncode}:\n{error_output}")
            
            if not output_path.exists():
                raise VideoGeneratorError("Output file was not created")
            
            if progress_callback:
                progress_callback("Video generation completed successfully")
            
            return output_path
            
        except subprocess.TimeoutExpired:
            raise VideoGeneratorError("FFmpeg execution timed out")
        except Exception as e:
            raise VideoGeneratorError(f"Video generation failed: {str(e)}")
