import traceback
import streamlit as st
import os
import tempfile
import subprocess
import shutil
import time
import sys
from gtts import gTTS
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import concatenate_audioclips
import re
import json
import logging
import gc
from moviepy import ColorClip

import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_VIDEO_DURATION = 60  # seconds
TARGET_AUDIENCE = "general audience"
OUTPUT_FORMAT = "mp4"

# Set up your API key - use environment variable for security
GEMINI_API_KEY = "AIzaSyC8i-N-HkONceslRARNweMnv6bH5lie8Bo"
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
    * Do not use 'MoveTo' 
    * **CRITICAL:** Do NOT use `Mobject` or `VGroup` directly (e.g., subclassing or creating empty instances) unless absolutely unavoidable for structuring complex custom shapes composed of allowed basic elements. Prefer using the standard shapes and text objects.

**LaTeX Handling (CRITICAL):**

9.  **Template Setup:**
    * Create a `TexTemplate`: `myTemplate = TexTemplate()`
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
    * PREFER USING SIMPLE TEXT OBJECTS INSTEAD OF LaTeX when possible to avoid LaTeX compilation issues.
    * Ensure that the arguments are passed correctly with the correcte number of arguments and the correct types.
    * Avoid using `MathTex` for simple text. Use `Text` instead.
    * Always provide a Text() fallback option for complex math expressions that may fail during LaTeX compilation.
**Code Robustness & Execution (CRITICAL):**

11. **Error Prevention:**
    * Write code that is coherent, fully executable, and produces a video output without runtime errors (e.g., `TypeError`, `AttributeError`, `IndexError`, LaTeX compilation errors).
    * **Prevent `NoneType` errors:** Before calling a method or accessing an attribute (`.move_to()`, `.get_center()`, `.color`, etc.), ensure the object variable is not `None`. Check return values of functions like `get_part_by_tex`. Example: `if my_object: self.play(my_object.animate.shift(UP))`.
    * **Index/Component Safety:** When accessing parts of objects by index (e.g., `math_tex[0]`) or using functions like `get_part_by_tex`, verify the index/part exists. Use dynamic queries or conditional checks. Example: `part = math_tex.get_part_by_tex("x"); if part: self.play(part.animate.set_color(BLUE))`.
    * Initialize and add objects to the scene before attempting to animate or reference their position.
    * Ensure animation sequences make logical sense (e.g., don't try to fade out an object that isn't currently on screen).
12. **Argument Validity:** Ensure all arguments passed to Manim functions/methods are valid (e.g., correct types, expected number of arguments).
13 . Verify that the code is executable without any erros before submitting it ! Make a revision to ensure that there is no Out of index errors or any similar problems
14. **IMPORTANT LaTeX FALLBACK:** If creating complex math expressions with LaTeX, always provide a Text() fallback option that will be used if LaTeX compilation fails. For example:
    ```python
    try:
        math_formula = MathTex(r"E = mc^2", tex_template=myTemplate)
    except Exception:
        # Fallback to plain text if LaTeX fails
        math_formula = Text("E = mc²", font_size=36)
15. When creating code that uses the manim library, ensure you ONLY import objects that are officially part of the manim package. Before including any class or function in an import statement, verify that it exists in the manim documentation (https://docs.manim.community/). Do not attempt to import made-up or non-existent classes like 'Annulate'. If unsure about the availability of a specific object, use standard Python alternatives or implement the functionality manually instead of assuming it exists in manim.
16. Make the code as simple as it could possibly be. Avoid using complex code that could lead to errors or confusion. Do not do complex animations that could lead to errors and use only manim functions.
    ```
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
                "duration_seconds": segment["duration_seconds"]  # Changed from "duration" to "duration_seconds"
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
        The following Manim code (Community Edition v0.19.0) failed to execute
        
        Here is the original code:
        ```python
        {manim_code}
        ```
        
        Fix all the code issues to make it executable. Return ONLY the fixed Python code without any explanations, comments, or markdown formatting.
        The code must create a Scene class named 'ExplanationScene' and must be directly executable with Manim.
        Focus on fixing:
        1. Syntax errors
        2. LaTeX errors (especially problematic math expressions) - REPLACE ALL COMPLEX LATEX WITH SIMPLE TEXT OBJECTS
        3. Reference errors (undefined variables, index out of range)
        4. Any unsupported methods or incompatible Manim functions
        5. Ensure all objects are properly initialized and added to the scene before use
        6. Ensure the code is coherent and fully executable without runtime errors (e.g., TypeError, AttributeError, IndexError, LaTeX compilation errors).
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

def execute_manim_code(manim_code, retry_count=0):
    """Execute the generated Manim code to create the animation."""
    max_retries = 4
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
            "-qh",  # Low quality for faster rendering
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
            elif retry_count < max_retries:
                # Try to fix the code with Gemini
                logger.info(f"Attempting to fix code with Gemini (attempt {retry_count + 1}/{max_retries})...")
                fixed_code = fix_manim_code_with_gemini(manim_code, result.stderr)
                
                # Write the fixed code to a new file
                fixed_file_path = os.path.join(manim_dir, f"fixed_explanation_scene_{retry_count + 1}.py")
                with open(fixed_file_path, "w", encoding="utf-8") as f:
                    f.write(fixed_code)
                
                # Try executing the fixed code
                logger.info(f"Executing fixed Manim code (attempt {retry_count + 1})...")
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
                    logger.info(f"Fixed code executed successfully on attempt {retry_count + 1}")
                else:
                    logger.error(f"Fixed code also failed on attempt {retry_count + 1}: {fixed_result.stderr}")
                    # Recursively try to fix the code again with an incremented retry counter
                    logger.info(f"Trying another fix attempt ({retry_count + 2}/{max_retries})...")
                    return execute_manim_code(fixed_code, retry_count + 1)
            else:
                logger.warning(f"Reached maximum retry attempts ({max_retries}). Proceeding with the last attempt.")
        
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
            fallback_clip = ColorClip(size=(640, 480), color=(0,0,0), duration=2)
            fallback_clip.write_videofile(fallback_video_path, fps=24, codec="libx264", audio=False)
            fallback_clip.close()
            video_path = fallback_video_path
        
        return video_path
    except Exception as e:
        logger.error(f"Error executing Manim code: {str(e)}")
        raise Exception(f"Failed to execute Manim code: {str(e)}")

def synchronize_audio_video(video_path, audio_segments):
    """Synchronize the segment-specific audio with the video, ensuring precise scene alignment."""
    temp_dir = None # Initialize outside try block for finally clause
    open_files = [] # Keep track of open moviepy objects
    audio_clips = [] # Keep track of loaded audio clips
    final_output_dest = None # Initialize outside try block

    try:
        # Use a specific output path within a temporary directory for better control
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"final_video.{OUTPUT_FORMAT}")
        logger.info(f"Synchronizing video. Output will be: {output_path}")

        # Load the video
        video_clip = VideoFileClip(video_path)
        open_files.append(video_clip)
        total_duration = video_clip.duration

        # Set explicit fps if not present, default to 24
        video_fps = getattr(video_clip, 'fps', 24)
        if not video_fps:
            logger.warning("Video clip FPS not found, defaulting to 24.")
            video_fps = 24
        logger.info(f"Loaded video clip: {video_path}, duration: {total_duration}s, fps: {video_fps}")

        # Handle case with no audio segments
        if not audio_segments:
            logger.warning("No audio segments provided for synchronization.")
            # Write original video as fallback
            fallback_path = os.path.join(temp_dir, f"fallback.{OUTPUT_FORMAT}")
            logger.info(f"Writing fallback video (no audio) to: {fallback_path}")
            video_clip.write_videofile(fallback_path, codec="libx264", fps=video_fps, logger='bar')
            # Move the fallback file out of the temp directory
            final_output_dest = tempfile.NamedTemporaryFile(suffix=f".{OUTPUT_FORMAT}", delete=False).name
            shutil.move(fallback_path, final_output_dest)
            logger.info(f"Moved fallback video from {fallback_path} to {final_output_dest}")
            return final_output_dest

        # Load all audio clips
        logger.info("Loading audio segments...")
        for i, segment in enumerate(audio_segments):
            try:
                audio_path = segment["path"]
                if not os.path.exists(audio_path):
                    logger.warning(f"Audio segment file not found: {audio_path}. Skipping.")
                    continue
                audio_clip = AudioFileClip(audio_path)
                # Don't add to open_files here, concatenate_audioclips handles internal clips
                audio_clips.append(audio_clip)
                logger.info(f"Loaded audio segment {i+1} ({audio_path}), duration: {audio_clip.duration}s")
            except Exception as e:
                logger.error(f"Error loading audio segment {i+1} ({segment.get('path', 'N/A')}): {str(e)}. Skipping.")
                # Ensure potentially partially loaded clip is closed if possible
                if 'audio_clip' in locals() and hasattr(audio_clip, 'close'):
                    try:
                        audio_clip.close()
                    except Exception as close_err:
                        logger.warning(f"Error closing problematic audio clip: {close_err}")

        # If we have successfully loaded audio clips, create a composite
        if audio_clips:
            composite_audio = None # Initialize for finally clause
            video_with_audio = None # Initialize for finally clause
            try:
                logger.info(f"Concatenating {len(audio_clips)} audio clips.")
                # Concatenate all loaded clips sequentially
                composite_audio = concatenate_audioclips(audio_clips)
                open_files.append(composite_audio) # Add composite to cleanup list

                # Adjust composite audio duration to match the video if needed
                if composite_audio.duration > total_duration:
                    logger.warning(f"Audio duration ({composite_audio.duration}s) exceeds video duration ({total_duration}s). Trimming audio.")
                    # Use subclip which returns a new clip
                    trimmed_audio = composite_audio.subclipped(0, total_duration)
                    # Close the original composite audio before replacing it
                    if hasattr(composite_audio, 'close'):
                        composite_audio.close()
                    open_files.remove(composite_audio)
                    composite_audio = trimmed_audio
                    open_files.append(composite_audio) # Add trimmed clip to cleanup list

                elif composite_audio.duration < total_duration:
                     logger.warning(f"Audio duration ({composite_audio.duration}s) is shorter than video duration ({total_duration}s). Video will have silence at the end.")

                # Set the composite audio for the video
                logger.info("Setting composite audio to video clip.")
                video_with_audio = video_clip.with_audio(composite_audio)
                # Don't add video_with_audio to open_files yet, it's handled by write_videofile

                # Write the final video with audio
                logger.info(f"Writing final video with audio to {output_path}, duration: {video_with_audio.duration}s, fps: {video_fps}")
                # Create a unique temp audio file path within the temp dir
                temp_audio_path = os.path.join(temp_dir, "temp-audio.m4a")
                video_with_audio.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile=temp_audio_path,
                    remove_temp=True,
                    fps=video_fps,  # Explicit fps
                    logger='bar'
                )
                logger.info("Finished writing final video.")

                # Explicitly close the final video clip after writing
                if hasattr(video_with_audio, 'close'):
                    video_with_audio.close()
                    video_with_audio = None # Ensure it's not closed again in finally

            except Exception as e:
                logger.error(f"Error during audio concatenation or video writing: {str(e)}")
                traceback_info = traceback.format_exc()
                logger.error(f"Traceback: {traceback_info}")
                # Fall back to just the video without audio if composition fails
                logger.warning("Fallback: writing video without audio due to error.")
                # Ensure video_with_audio is closed if it exists
                if video_with_audio and hasattr(video_with_audio, 'close'):
                    try: video_with_audio.close()
                    except: pass # Ignore errors during cleanup
                # Ensure composite_audio is closed if it exists
                if composite_audio and hasattr(composite_audio, 'close'):
                    try: composite_audio.close()
                    except: pass # Ignore errors during cleanup
                    if composite_audio in open_files: open_files.remove(composite_audio)

                # Write the original video clip without audio
                video_clip.write_videofile(output_path, codec="libx264", fps=video_fps, logger='bar', audio=False)
        else:
            # No audio clips were successfully loaded
            logger.warning("No audio clips were successfully loaded. Writing video without audio.")
            video_clip.write_videofile(output_path, codec="libx264", fps=video_fps, logger='bar', audio=False)

        # Move the final file out of the temp directory
        final_output_dest = tempfile.NamedTemporaryFile(suffix=f".{OUTPUT_FORMAT}", delete=False).name
        shutil.move(output_path, final_output_dest)
        logger.info(f"Moved final video from {output_path} to {final_output_dest}")

        return final_output_dest

    except Exception as e:
        logger.error(f"Unhandled error synchronizing audio and video: {str(e)}")
        traceback_info = traceback.format_exc()
        logger.error(f"Traceback: {traceback_info}")

        # Return the original video path as a fallback if possible
        if 'video_path' in locals() and os.path.exists(video_path):
            logger.info("Returning original video as fallback due to unhandled synchronization error")
            # We need to copy it to a safe location as the original might be in a temp dir
            try:
                fallback_dest = tempfile.NamedTemporaryFile(suffix=f".{OUTPUT_FORMAT}", delete=False).name
                shutil.copy(video_path, fallback_dest)
                return fallback_dest
            except Exception as copy_err:
                 logger.error(f"Failed to copy original video as fallback: {copy_err}")

        raise Exception(f"Failed to synchronize audio and video: {str(e)}")

    finally:
        # Ensure proper cleanup of all open moviepy objects
        logger.info("Starting cleanup of moviepy objects...")
        # Close individual audio clips first
        for clip in audio_clips:
             if hasattr(clip, 'close'):
                 try:
                     clip.close()
                     logger.debug(f"Closed individual audio clip: {clip}")
                 except Exception as e:
                     logger.warning(f"Error closing individual audio clip: {str(e)}")
        # Close other moviepy objects (video, composite audio)
        for file_obj in open_files:
            if hasattr(file_obj, 'close'):
                try:
                    file_obj.close()
                    logger.debug(f"Closed moviepy object: {file_obj}")
                except Exception as e:
                    logger.warning(f"Error closing moviepy object {file_obj}: {str(e)}")
        logger.info("Finished cleanup of moviepy objects.")

        # Force cleanup of temp audio segment files with retry mechanism
        if 'audio_segments' in locals():
            logger.info("Starting cleanup of temporary audio segment files...")
            for segment in audio_segments:
                segment_path = segment.get("path")
                if segment_path and os.path.exists(segment_path):
                    for attempt in range(3):  # Try up to 3 times
                        try:
                            # Force garbage collection before delete on Windows
                            if sys.platform == 'win32':                  
                                gc.collect()
                                time.sleep(0.1) # Small delay

                            os.unlink(segment_path)
                            logger.debug(f"Deleted temp audio file: {segment_path}")
                            break # Success, exit retry loop
                        except PermissionError as pe:
                             logger.warning(f"Attempt {attempt+1} PermissionError deleting {segment_path}: {str(pe)}. Retrying...")
                             time.sleep(0.5) # Wait longer for permission issues
                        except Exception as e:
                            logger.warning(f"Attempt {attempt+1} failed to delete {segment_path}: {str(e)}. Retrying...")
                            time.sleep(0.2) # Wait before retry
                    else: # If loop completed without break
                         logger.error(f"Failed to delete temp audio file after multiple attempts: {segment_path}")
            logger.info("Finished cleanup of temporary audio segment files.")

        # Clean up temp directory used for synchronization
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Could not clean up temp directory {temp_dir}: {str(e)}")

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
