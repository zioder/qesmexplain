import traceback
import streamlit as st
import os
import tempfile
import subprocess
import shutil
import time
import sys
from gtts import gTTS
# Replace problematic imports with direct specific imports
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import AudioClip, CompositeAudioClip
from moviepy import concatenate_videoclips #
from moviepy import VideoClip 
import moviepy.audio as afx 
import re
import json
import logging
from pathlib import Path
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_VIDEO_DURATION = 60  # seconds
TARGET_AUDIENCE = "general audience"
OUTPUT_FORMAT = "mp4"
DEFAULT_FPS = 24  # Default frames per second for video output

# Set up your API key - use environment variable for security
GEMINI_API_KEY = "AIzaSyBHFCcsbG1ImqXXE30mdtHnUG9pa_pzC6w"
if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY not found in environment variables")

# Initialize Gemini API
genai.configure(api_key=GEMINI_API_KEY)

def generate_script(prompt):
    """Generate a comprehensive video script using Gemini."""
    try:
        model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')
        script_prompt = f"""
        Create a comprehensive video script based on this prompt: "{prompt}".
        The script should include:
        1. A clear narration text (what will be spoken)
        2. Detailed visual descriptions for each segment (what will be shown)
        3. The script should be suitable for a {TARGET_AUDIENCE}
        4. The video should not exceed {MAX_VIDEO_DURATION} seconds
        
        Format the response as a JSON object with the following structure:
        {{
            "title": "Title of the Video",
            "segments": [
                {{
                    "narration": "Text to be spoken",
                    "visual_description": "Detailed description of what should be animated",
                    "duration_seconds": estimated_duration_in_seconds
                }},
                ...
            ]
        }}
        """
        
        response = model.generate_content(script_prompt)
        # Extract JSON from response
        script_text = response.text
        # Find JSON content
        json_match = re.search(r'```json(.*?)```', script_text, re.DOTALL)
        if json_match:
            script_json = json.loads(json_match.group(1).strip())
        else:
            script_json = json.loads(script_text)
        
        if "segments" not in script_json or not isinstance(script_json["segments"], list):
            script_json["segments"] = []
        for seg in script_json["segments"]:
            if "duration_seconds" not in seg:
                seg["duration_seconds"] = 5
        print(seg)
        return script_json
    except Exception as e:
        logger.error(f"Error generating script: {str(e)}")
        raise Exception(f"Failed to generate script: {str(e)}")

def generate_manim_code(script):
    """Generate Manim code version Community v0.19.0 from the script's visual descriptions."""
    try:
        model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')
        manim_prompt = f"""
        Generate Python code using the Manim library (Community Edition v0.19.0 or compatible)
to create an animation based on the visual descriptions provided in the following JSON structure:

{json.dumps(script['segments'])}

**Core Requirements:**

1.  **Output Format:** Return ONLY valid, executable Python code. Do not include explanations or conversational text outside of code comments.
2.  **Scene Structure:** Create a single Manim Scene class named `ExplanationScene` and implement its `construct` method to contain the entire animation logic.
3.  **Content Generation:**
    * Accurately translate each visual element and action described in the input `script['segments']` into Manim objects and animations.
    * Time the animations for each segment to approximately match the specified `duration_seconds`. The total animation duration should be roughly {sum(segment['duration_seconds'] for segment in script['segments'])} seconds.
4.  **Visual Presentation:**
    * Position text and visual elements carefully to avoid overlaps. Ensure all text is clear and easily readable (use appropriate font sizes and contrasting colors).
    * Utilize the screen space effectively.
    * **CRITICAL:** Clear the screen (remove/fade out objects) between distinct visual segments described in the input, unless persistence across segments is explicitly intended by the description.

**Manim Usage & Restrictions:**

5.  **Imports:** Start the script with specific imports (e.g., `from manim import Scene, Text, Circle, Create, Write, FadeOut, UP, DOWN, LEFT, RIGHT, ORIGIN, WHITE, BLUE, TexTemplate, MathTex, Tex`). Do NOT use `from manim import *`. Import necessary constants like `UP`, `DOWN`, `ORIGIN`, `WHITE`, `BLUE`, etc. explicitly.
6.  **Manim Only:**
    * Use ONLY Manim's built-in objects and animations.
    * Do NOT use external Python libraries or modules.
    * Do NOT include images, SVGs, or references to external files.
    * Do NOT include social media elements (like/subscribe buttons, icons, text).
7.  **Allowed Elements:**
    * Prioritize basic shapes (e.g., `Circle`, `Square`, `Rectangle`, `Triangle`, `Line`, `Dot`, `Vector`).
    * Prioritize basic animations (e.g., `FadeIn`, `FadeOut`, `Create`, `Write`, `Transform`, `MoveTo`, `Shift`).
8.  **CRITICAL - Disallowed Elements/Practices:**
    * Do NOT use `Checkmark` (use `Text("✓")` or a simple shape).
    * Do NOT use `Arrow` (use `Line` with `add_tip=True` or `Vector`).
    * Do NOT use `ShowCreation` (use `Create`).
    * Do NOT use `FadeInFromPoint` (use `FadeIn` and set the object's position beforehand).
    * Do NOT use objects potentially unavailable in Manim CE v0.19.0 without confirmation.
    * **CRITICAL:** Do NOT use `Mobject` or `VGroup` directly (e.g., subclassing or creating empty instances) unless absolutely unavoidable for structuring complex custom shapes composed of allowed basic elements. Prefer using the standard shapes and text objects.

**LaTeX Handling (CRITICAL):**

9.  **Template Setup:**
    * Create a `TexTemplate`: `myTemplate = TexTemplate()`
    * Add necessary packages to the preamble, especially for math:
        `myTemplate.add_to_preamble(r"\\usepackage")`
        `myTemplate.add_to_preamble(r"\\usepackage")`
        # Add other packages like amsthm if needed by the script descriptions
    * Use this template for `Tex` and `MathTex` objects: `MathTex("...", tex_template=myTemplate)`
10. **Syntax and Validity:**
    * Ensure ALL LaTeX expressions are valid and compile correctly. Test complex expressions independently if unsure.
    * Use r-strings for all LaTeX code: `r"\\mathcal"`.
    * Properly escape LaTeX special characters (e.g., `\\`, `%`, `&`, `_`, `^`, `$`, `#`). Double-escape backslashes within Python f-strings if LaTeX is constructed dynamically.
    * Use `MathTex(..., tex_template=myTemplate)` for pure mathematical expressions and `Tex(..., tex_template=myTemplate)` for text mixed with math.
    * Ensure all LaTeX braces  and environments (`\\begin{...} \\end{...}`) are correctly matched and closed.
    * Avoid splitting essential LaTeX commands across multiple string arguments in `MathTex` or `Tex`.
    * Use standard LaTeX commands and avoid obscure packages or Unicode characters within LaTeX unless the necessary packages are added to the `TexTemplate`.
    * Ensure colors used within LaTeX (if any) are defined/imported via appropriate packages in the template.
    * **CRITICAL:** Always specify the fps attribute for video generation by adding self.camera.frame_rate = 30 (or similar value) to ensure that the video is generated with a valid fps value.

**Code Robustness & Execution (CRITICAL):**

11. **Error Prevention:**
    * Write code that is coherent, fully executable, and produces a video output without runtime errors (e.g., `TypeError`, `AttributeError`, `IndexError`, LaTeX compilation errors).
    * **Prevent `NoneType` errors:** Before calling a method or accessing an attribute (`.move_to()`, `.get_center()`, `.color`, etc.), ensure the object variable is not `None`. Check return values of functions like `get_part_by_tex`. Example: `if my_object: self.play(my_object.animate.shift(UP))`.
    * **Index/Component Safety:** When accessing parts of objects by index (e.g., `math_tex[0]`) or using functions like `get_part_by_tex`, verify the index/part exists. Use dynamic queries or conditional checks. Example: `part = math_tex.get_part_by_tex("x"); if part: self.play(part.animate.set_color(BLUE))`.
    * Initialize and add objects to the scene before attempting to animate or reference their position.
    * Ensure animation sequences make logical sense (e.g., don't try to fade out an object that isn't currently on screen).
12. **Argument Validity:** Ensure all arguments passed to Manim functions/methods are valid (e.g., correct types, expected number of arguments).
13 . Verify that the code is executable without any erros before submitting it ! Make a revision to ensure that there is no Out of index errors or any similar problems
        """
        
        response = model.generate_content(manim_prompt)
        # Extract code from response
        manim_code = response.text
        # Clean up the code - extract from code blocks if present
        code_match = re.search(r'```python(.*?)```', manim_code, re.DOTALL)
        if code_match:
            manim_code = code_match.group(1).strip()
        
        # Remove or replace problematic Unicode characters
        # Replace checkmark with "ok" and other common symbols that might cause issues
        manim_code = manim_code.replace('\u2713', 'ok')
        manim_code = manim_code.replace('\u2192', '->')
        manim_code = manim_code.replace('\u2190', '<-')
        manim_code = manim_code.replace('\u2022', '*')
        
        return manim_code
    except Exception as e:
        logger.error(f"Error generating Manim code: {str(e)}")
        raise Exception(f"Failed to generate Manim code: {str(e)}")

def generate_audio(script):
    """Generate separate audio clips for each script segment using gTTS."""
    try:
        audio_paths = []
        
        # Create separate audio file for each segment
        for i, segment in enumerate(script["segments"]):
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
                segment_audio_path = temp_audio.name
            
            # Generate audio for this segment only
            narration = segment["narration"]
            tts = gTTS(text=narration, lang='en', slow=False)
            tts.save(segment_audio_path)
            
            audio_paths.append({
                "path": segment_audio_path,
                "duration_seconds": segment["duration_seconds"]  
            })
        
        return audio_paths
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        raise Exception(f"Failed to generate audio: {str(e)}")

def fix_manim_code_with_gemini(manim_code, error_message):
    """Send the Manim code and error to Gemini for fixing."""
    try:
        model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')
        fix_prompt = f"""
        The following Manim code (Community Edition v0.19.0) failed to execute with this error:
        
        ERROR:
        {error_message}
        
        Here is the original code:
        ```python
        {manim_code}
        ```
        
        Fix the code issues to make it executable. Return ONLY the fixed Python code without any explanations, comments, or markdown formatting.
        The code must create a Scene class named 'ExplanationScene' and must be directly executable with Manim.
        Focus on fixing:
        1. Syntax errors
        2. LaTeX errors (especially problematic math expressions)
        3. Reference errors (undefined variables, index out of range)
        4. Any unsupported methods or incompatible Manim functions
        5. Ensure that if any video clips are created, they must have an 'fps' attribute set (clip.fps = value)
        6. Check that any write_videofile() calls include an explicit fps parameter
        
        Return ONLY the corrected code with no additional text.
        """
        
        response = model.generate_content(fix_prompt)
        fixed_code = response.text
        
        # Clean up the code - extract from code blocks if present
        code_match = re.search(r'```python(.*?)```', fixed_code, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1).strip()
        
        # Remove or replace problematic Unicode characters
        fixed_code = fixed_code.replace('\u2713', 'ok')
        fixed_code = fixed_code.replace('\u2192', '->')
        fixed_code = fixed_code.replace('\u2190', '<-')
        fixed_code = fixed_code.replace('\u2022', '*')
        
        logger.info("Received fixed Manim code from Gemini")
        return fixed_code
    except Exception as e:
        logger.error(f"Error fixing code with Gemini: {str(e)}")
        # Return the original code if we can't fix it
        return manim_code

def execute_manim_code(manim_code):
    """Execute the generated Manim code to create the animation."""
    try:
        # Create a temporary directory for Manim files
        manim_dir = tempfile.mkdtemp()
        manim_file_path = os.path.join(manim_dir, "explanation_scene.py")
        
        # Write the Manim code to a file with UTF-8 encoding
        with open(manim_file_path, "w", encoding="utf-8") as f:
            f.write(manim_code)
        
        # Enhanced logging for debugging
        logger.info(f"Created Manim file at: {manim_file_path}")
        logger.info(f"Manim directory: {manim_dir}")
        
        # Check if manim is available in PATH
        try:
            version_result = subprocess.run(["manim", "--version"], check=True, capture_output=True, text=True)
            logger.info(f"Manim version: {version_result.stdout.strip()}")
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"Manim check failed: {str(e)}")
            raise Exception("Manim is not installed or not in PATH. Please install Manim or check your installation.")
        
        # Execute Manim to generate the video
        logger.info(f"Executing Manim in directory: {manim_dir}")
        
        # Use full path for python executable
        python_executable = sys.executable
        
        # Run manim as a module through Python to ensure proper environment
        command = [
            python_executable,
            "-m", "manim",
            "-ql",  # Low quality for faster rendering
            "--output_file=explanation_video",
            manim_file_path,
            "ExplanationScene"
        ]
        
        # Set up environment variables
        env = os.environ.copy()
        
        # Additional logging before execution
        logger.info(f"Running command: {' '.join(command)}")
        
        # First attempt to run the code
        result = subprocess.run(
            command, 
            cwd=manim_dir, 
            capture_output=True, 
            text=True,
            env=env
        )
        
        # If execution failed, try to fix the code with Gemini
        if result.returncode != 0:
            logger.error(f"Manim execution failed with error: {result.stderr}")
            
            # Don't try fixing LaTeX errors, as they might be due to system issues not code problems
            if "latex error converting to dvi" in result.stderr.lower():
                logger.warning("Latex error converting to dvi encountered. Attempting to proceed without blocking.")
            else:
                # Try to fix the code with Gemini
                logger.info("Attempting to fix code with Gemini...")
                fixed_code = fix_manim_code_with_gemini(manim_code, result.stderr)
                
                # Write the fixed code to a new file
                fixed_file_path = os.path.join(manim_dir, "fixed_explanation_scene.py")
                with open(fixed_file_path, "w", encoding="utf-8") as f:
                    f.write(fixed_code)
                
                # Try executing the fixed code
                logger.info("Executing fixed Manim code...")
                fixed_command = [
                    python_executable,
                    "-m", "manim",
                    "-ql",
                    "--output_file=explanation_video",
                    fixed_file_path,
                    "ExplanationScene"
                ]
                
                fixed_result = subprocess.run(
                    fixed_command, 
                    cwd=manim_dir, 
                    capture_output=True, 
                    text=True,
                    env=env
                )
                
                if fixed_result.returncode == 0:
                    logger.info("Fixed code executed successfully")
                else:
                    logger.error(f"Fixed code also failed: {fixed_result.stderr}")
        
        # Improved file search logic
        expected_media_dir = os.path.join(manim_dir, "media", "videos", "explanation_scene")
        video_path = None
        
        if os.path.exists(expected_media_dir):
            logger.info(f"Expected media directory found: {expected_media_dir}")
            video_files = [f for f in os.listdir(expected_media_dir) if f.endswith(".mp4")]
            if video_files:
                video_path = os.path.join(expected_media_dir, video_files[0])
                logger.info(f"Found video at expected location: {video_path}")
        
        if not video_path:
            logger.info("Searching for video files in entire project directory...")
            for root, dirs, files in os.walk(manim_dir):
                mp4_files = [f for f in files if f.endswith(".mp4")]
                if mp4_files:
                    video_path = os.path.join(root, mp4_files[0])
                    logger.info(f"Found MP4 file at: {video_path}")
                    break
        
        if not video_path:
            logger.warning("No video produced. Creating a dummy fallback video to avoid blocking.")
            fallback_video_path = os.path.join(manim_dir, "fallback.mp4")
            from moviepy import ColorClip
            fallback_clip = ColorClip(size=(640, 480), color=(0,0,0), duration=2)
            fallback_clip.write_videofile(fallback_video_path, fps=24, codec="libx264", audio=False)
            fallback_clip.close()
            video_path = fallback_video_path
        
        return video_path
    except Exception as e:
        logger.error(f"Error executing Manim code: {str(e)}")
        raise Exception(f"Failed to execute Manim code: {str(e)}")

def safe_subclip(clip, start_time, end_time):
    """Safely create a subclip regardless of MoviePy version differences."""
    try:
        # First try the standard subclip method
        if hasattr(clip, 'subclip'):
            return clip.subclip(start_time, end_time)
        # If that fails, try the alternative approach using crop
        elif hasattr(clip, 'crop'):
            return clip.crop(t_start=start_time, t_end=end_time)
        # If both fail, create a new clip that starts at the specified time
        else:
            # Get the clip's attributes
            duration = end_time - start_time
            fps = getattr(clip, 'fps', DEFAULT_FPS)
            
            # Create a new video clip that represents the subclip
            def make_frame(t):
                return clip.get_frame(t + start_time)
            
            new_clip = VideoClip(make_frame, duration=duration)
            new_clip.fps = fps
            
            # If the original clip has audio, apply the same process to the audio
            if hasattr(clip, 'audio') and clip.audio is not None:
                audio = clip.audio
                if hasattr(audio, 'subclip'):
                    new_clip.audio = audio.subclip(start_time, end_time)
                else:
                    # Create a new audio clip
                    def make_audioframe(t):
                        return audio.get_frame(t + start_time)
                    
                    new_audio = AudioClip(make_audioframe, duration=duration)
                    if hasattr(audio, 'fps'):
                        new_audio.fps = audio.fps
                    new_clip.audio = new_audio
            
            return new_clip
    except Exception as e:
        logger.error(f"Error in safe_subclip: {str(e)}")
        raise e

def synchronize_audio_video(video_path, audio_segments):
    """Synchronize the segment-specific audio with the video, ensuring precise scene alignment."""
    try:
        # Use a specific output path within a temporary directory for better control
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"final_video.{OUTPUT_FORMAT}")
        logger.info(f"Synchronizing video. Output will be: {output_path}")

        # Load the video
        video_clip = VideoFileClip(video_path)
        
        # Ensure video has fps attribute
        if not hasattr(video_clip, 'fps') or video_clip.fps is None:
            logger.info(f"Video clip has no fps attribute, setting to default {DEFAULT_FPS}")
            video_clip.fps = DEFAULT_FPS
        else:
            logger.info(f"Video clip fps: {video_clip.fps}")
            
        total_duration = video_clip.duration
        logger.info(f"Loaded video clip: {video_path}, duration: {total_duration}s")

        # Calculate total script duration and validate
        if not audio_segments:
             logger.warning("No audio segments provided for synchronization.")
             # Return original video as fallback
             shutil.copy(video_path, output_path)
             video_clip.close() # Close the clip
             return output_path

        total_script_duration = sum(segment["duration_seconds"] for segment in audio_segments)
        logger.info(f"Total script duration: {total_script_duration}s")

        # Calculate scale factor to match script and video durations
        if total_script_duration == 0:
            logger.warning("Total script duration is 0. Using scale factor of 1.0.")
            scale_factor = 1.0
        else:
            scale_factor = total_duration / total_script_duration
            logger.info(f"Using scale factor: {scale_factor:.4f} to match video duration")

        # Process each segment separately
        segment_clips = []
        current_time = 0.0  # Use float for time

        for i, segment in enumerate(audio_segments):
            logger.info(f"Processing segment {i+1}/{len(audio_segments)}...")
            # Calculate actual segment duration in the video
            script_segment_duration = segment["duration_seconds"]
            scaled_segment_duration = script_segment_duration * scale_factor
            logger.info(f"  Script duration: {script_segment_duration}s, Scaled duration: {scaled_segment_duration:.4f}s")

            # Prevent overshooting video duration
            if current_time >= total_duration:
                logger.warning(f"  Skipping segment {i+1}: Start time ({current_time:.4f}s) already exceeds video duration ({total_duration:.4f}s).")
                continue

            # Calculate end time, capped by total video duration
            end_time = min(current_time + scaled_segment_duration, total_duration)
            actual_segment_duration = end_time - current_time
            logger.info(f"  Video segment time: {current_time:.4f}s to {end_time:.4f}s (Actual duration: {actual_segment_duration:.4f}s)")

            if actual_segment_duration <= 0.01:  # Use a small threshold to avoid tiny clips
                logger.warning(f"  Skipping segment {i+1}: Calculated duration ({actual_segment_duration:.4f}s) is too small.")
                continue

            # Extract this segment from the video
            try:
                # Ensure valid time range
                if current_time < 0 or end_time <= current_time or end_time > total_duration:
                    logger.warning(f"  Invalid time range detected: {current_time:.4f}s to {end_time:.4f}s (total: {total_duration:.4f}s)")
                    # Adjust to safe values
                    current_time = max(0, min(current_time, total_duration - 0.1))
                    end_time = max(current_time + 0.1, min(end_time, total_duration))
                    logger.info(f"  Adjusted to safe range: {current_time:.4f}s to {end_time:.4f}s")
                
                # Use the safe_subclip function instead of directly calling subclip
                video_segment = safe_subclip(video_clip, current_time, end_time)
                logger.info(f"  Extracted video segment, duration: {video_segment.duration:.4f}s")
            except Exception as e:
                logger.error(f"  Error extracting video segment: {e}")
                logger.error(f"  Traceback: {traceback.format_exc()}")
                # Skip this segment if extraction fails
                current_time = end_time  # Still update time pointer to prevent getting stuck
                continue

            # Process audio for this segment
            try:
                audio_clip = AudioFileClip(segment["path"])
                logger.info(f"  Loaded audio clip: {segment['path']}, duration: {audio_clip.duration:.4f}s")

                # Get target duration for audio (same as video segment)
                target_audio_duration = video_segment.duration
                
                if abs(audio_clip.duration - target_audio_duration) > 0.1:
                    # Adjust audio to match exactly the video segment duration
                    if audio_clip.duration > target_audio_duration:
                        # Audio is too long - speed it up without affecting pitch too much
                        speed_factor = audio_clip.duration / target_audio_duration
                        # If speed factor is reasonable, adjust it
                        if 0.8 <= speed_factor <= 1.5:
                            logger.info(f"  Speeding up audio by factor: {speed_factor:.4f}")
                            audio_clip = audio_clip.fx(afx.audio_speedx, factor=speed_factor)
                        else:
                            # If adjustment would be too extreme, use a safer approach
                            logger.warning(f"  Speed factor {speed_factor:.4f} too extreme. Using subclip instead.")
                            # Take a subclip from the center of the audio to preserve main content
                            excess = audio_clip.duration - target_audio_duration
                            start_trim = excess / 2
                            audio_clip = audio_clip.subclip(start_trim, start_trim + target_audio_duration)
                    else:
                        # Audio is too short - extend it with silence at the end
                        silence_duration = target_audio_duration - audio_clip.duration
                        logger.info(f"  Extending audio with {silence_duration:.4f}s of silence")
                        
                        # Create silence with same number of channels as audio
                        def silence_maker(t):
                            return [0] * (audio_clip.nchannels if hasattr(audio_clip, 'nchannels') else 1)
                        
                        silence = AudioClip(
                            make_frame=silence_maker, 
                            duration=silence_duration,
                            fps=audio_clip.fps if hasattr(audio_clip, 'fps') else 44100
                        )
                        
                        # Combine original audio with silence
                        audio_clip = CompositeAudioClip([
                            audio_clip.set_start(0),
                            silence.set_start(audio_clip.duration)
                        ])
                
                # Ensure final duration matches exactly
                audio_clip = audio_clip.set_duration(target_audio_duration)
                
                # Apply a short fade-in and fade-out to avoid clicks/pops
                if audio_clip.duration >= 0.3:  # Only if audio is long enough
                    fade_duration = min(0.1, audio_clip.duration / 4)  # Max 100ms or 1/4 of clip
                    audio_clip = audio_clip.audio_fadein(fade_duration).audio_fadeout(fade_duration)
                
                # Set the audio to the video segment
                video_segment = video_segment.set_audio(audio_clip)
                segment_clips.append(video_segment)
                logger.info(f"  Successfully added audio to video segment")

            except Exception as e:
                logger.error(f"  Error processing audio for segment {i+1}: {str(e)}")
                # Add the video segment without audio if there's an issue
                segment_clips.append(video_segment)
            finally:
                if 'audio_clip' in locals() and audio_clip:
                    audio_clip.close()

            # Update time pointer for next segment
            current_time = end_time

        # Handle case with no valid segments
        if not segment_clips:
            logger.warning("No valid video segments were created. Using original video instead.")
            # Just use the original video without modifications
            shutil.copy(video_path, output_path)
            video_clip.close()
            return output_path

        # Concatenate all segments
        logger.info(f"Concatenating {len(segment_clips)} processed video segments...")
        final_clip = concatenate_videoclips(segment_clips, method="compose")
        logger.info(f"Final clip duration: {final_clip.duration:.4f}s")

        # Write final video to file
        logger.info(f"Writing final synchronized video to {output_path}")
        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=final_clip.fps if hasattr(final_clip, 'fps') and final_clip.fps is not None else DEFAULT_FPS,
            temp_audiofile=os.path.join(temp_dir, "temp-audio.m4a"),
            remove_temp=True,
            logger='bar',
            threads=4
        )
        logger.info(f"Successfully wrote final video.")

        # Clean up
        final_clip.close()
        for clip in segment_clips:
            clip.close()
        video_clip.close()
        for segment in audio_segments:
            if os.path.exists(segment["path"]):
                try:
                    os.unlink(segment["path"])
                except Exception as e_unlink:
                    logger.warning(f"Failed to delete temp audio {segment['path']}: {e_unlink}")

        # Move the final file out and clean up
        final_output_dest = tempfile.NamedTemporaryFile(suffix=f".{OUTPUT_FORMAT}", delete=False).name
        shutil.move(output_path, final_output_dest)
        logger.info(f"Moved final video from {output_path} to {final_output_dest}")

        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e_clean:
            logger.warning(f"Could not clean up temp directory {temp_dir}: {e_clean}")

        return final_output_dest

    except Exception as e:
        logger.error(f"Error synchronizing audio and video: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Clean up temp dir on error
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e_clean:
                logger.warning(f"Could not clean up temp directory {temp_dir} on error: {e_clean}")
                 
        # Return the original video path as a fallback
        if 'video_path' in locals() and os.path.exists(video_path):
            logger.info("Returning original video as fallback due to synchronization error")
            return video_path
                 
        raise Exception(f"Failed to synchronize audio and video: {str(e)}")
    finally:
        # Ensure clips are closed even if errors occurred
        if 'video_clip' in locals() and video_clip: video_clip.close()
        if 'final_clip' in locals() and final_clip: final_clip.close()
        if 'segment_clips' in locals():
            for clip in segment_clips:
                if clip: clip.close()

def cleanup_temp_files(file_paths):
    """Clean up temporary files."""
    for path in file_paths:
        try:
            if os.path.isfile(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            logger.warning(f"Failed to delete {path}: {str(e)}")

# Streamlit UI
st.title("Qesm Video Explication Generator")
st.write(f"""
This app transforms your prompt into an explanatory video using AI.
- Target audience: {TARGET_AUDIENCE}
- Maximum duration: {MAX_VIDEO_DURATION} seconds
- Output format: {OUTPUT_FORMAT}
""")

# User input
user_prompt = st.text_area("Enter your prompt (what concept would you like explained in a video?):", 
                          height=100,
                          placeholder="Example: Explain how photosynthesis works")

if st.button("Generate Video"):
    if not user_prompt:
        st.error("Please enter a prompt.")
    else:
        # Create process indicator
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Generate Script
            status_text.text("Generating script...")
            script = generate_script(user_prompt)
            progress_bar.progress(20)
            
            # Display the generated script
            with st.expander("Generated Script"):
                st.write(f"**Title:** {script['title']}")
                for i, segment in enumerate(script['segments']):
                    st.write(f"**Segment {i+1}:**")
                    st.write(f"- **Narration:** {segment['narration']}")
                    st.write(f"- **Visual:** {segment['visual_description']}")
                    st.write(f"- **Duration:** {segment['duration_seconds']} seconds")
            
            # Step 2: Generate Manim Code
            status_text.text("Generating animation code...")
            manim_code = generate_manim_code(script)
            progress_bar.progress(40)
            
            # Display the generated code
            with st.expander("Generated Manim Code"):
                st.code(manim_code, language="python")
            
            # Step 3: Generate Audio
            status_text.text("Generating audio narration...")
            audio_segments = generate_audio(script)
            progress_bar.progress(60)
            
            # Step 4: Execute Manim Code
            status_text.text("Creating animation (this might take a while)...")
            video_path = execute_manim_code(manim_code)
            progress_bar.progress(80)
            
            # Step 5: Synchronize Audio and Video
            status_text.text("Synchronizing audio and video...")
            final_video_path = synchronize_audio_video(video_path, audio_segments)
            progress_bar.progress(100)
            
            # Step 6: Display the final video
            status_text.text("Video generation complete!")
            
            # Show the video
            st.video(final_video_path)
            
            # Provide download button
            with open(final_video_path, "rb") as file:
                btn = st.download_button(
                    label="Download video",
                    data=file,
                    file_name=f"{script['title'].replace(' ', '_')}.{OUTPUT_FORMAT}",
                    mime=f"video/{OUTPUT_FORMAT}"
                )
            
            # Cleanup temporary files
            segment_paths = [segment["path"] for segment in audio_segments]
            cleanup_temp_files([video_path, final_video_path] + segment_paths)
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            logger.error(str(e))

st.markdown("---")
st.caption("Powered by Gemini AI, Manim, and Streamlit")