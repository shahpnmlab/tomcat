/**
 * TomCat Media Updater
 *
 * This script provides real-time updates for media (thumbnails, lowmag images,
 * tilt series animations, and tomogram animations) without requiring page reloads.
 */

// Configuration
const POLLING_INTERVAL = 2000; // Time in ms between status checks
const MAX_RETRIES = 30; // Maximum number of polling attempts per media
const DEBUG = false; // Set to true for detailed console logging

// Track media being monitored
const monitoredMedia = {
    thumbnails: new Map(), // tomo_name -> { element, attempts }
    media: new Map() // key (media_type_tomo_name) -> { element, attempts, mediaType, tomoName }
};

/**
 * Initialize media updater for all media elements on the page
 */
function initMediaUpdater() {
    // Find all placeholder images for thumbnails
    document.querySelectorAll('[data-thumbnail-name]').forEach(element => {
        const tomoName = element.getAttribute('data-thumbnail-name');
        if (tomoName) {
            monitoredMedia.thumbnails.set(tomoName, {
                element: element,
                attempts: 0
            });
            logDebug(`Monitoring thumbnail for ${tomoName}`);
        }
    });

    // Find all placeholder images for media (lowmag, tiltseries, tomogram)
    document.querySelectorAll('[data-media-type][data-tomo-name]').forEach(element => {
        const mediaType = element.getAttribute('data-media-type');
        const tomoName = element.getAttribute('data-tomo-name');

        if (mediaType && tomoName) {
            const key = `${mediaType}_${tomoName}`;
            monitoredMedia.media.set(key, {
                element: element,
                attempts: 0,
                mediaType: mediaType,
                tomoName: tomoName
            });
            logDebug(`Monitoring ${mediaType} for ${tomoName}`);
        }
    });

    // Start polling if we have media to monitor
    if (monitoredMedia.thumbnails.size > 0 || monitoredMedia.media.size > 0) {
        logDebug(`Starting media updater with ${monitoredMedia.thumbnails.size} thumbnails and ${monitoredMedia.media.size} media items`);
        startPolling();
    }
}

/**
 * Start polling for media updates
 */
function startPolling() {
    // Poll thumbnails
    if (monitoredMedia.thumbnails.size > 0) {
        pollThumbnails();
    }

    // Poll other media
    if (monitoredMedia.media.size > 0) {
        pollMedia();
    }

    // Continue polling at regular intervals
    setTimeout(startPolling, POLLING_INTERVAL);
}

/**
 * Poll for thumbnail updates
 */
function pollThumbnails() {
    // Process each thumbnail
    for (const [tomoName, data] of monitoredMedia.thumbnails.entries()) {
        // Skip if max attempts reached
        if (data.attempts >= MAX_RETRIES) {
            continue;
        }

        // Check thumbnail status
        fetch(`/thumbnail_status/${tomoName}`)
            .then(response => response.json())
            .then(statusData => {
                if (statusData.available) {
                    updateThumbnail(tomoName, statusData.path);
                } else {
                    // Increment attempt counter
                    data.attempts++;
                    logDebug(`Thumbnail for ${tomoName} not ready (attempt ${data.attempts}/${MAX_RETRIES})`);

                    // Remove from monitoring if max attempts reached
                    if (data.attempts >= MAX_RETRIES) {
                        logDebug(`Giving up on thumbnail for ${tomoName} after ${MAX_RETRIES} attempts`);
                    }
                }
            })
            .catch(error => {
                console.error(`Error checking thumbnail status for ${tomoName}:`, error);
            });
    }
}

/**
 * Poll for media updates (lowmag, tiltseries, tomogram)
 */
function pollMedia() {
    // Process each media item
    for (const [key, data] of monitoredMedia.media.entries()) {
        // Skip if max attempts reached
        if (data.attempts >= MAX_RETRIES) {
            continue;
        }

        const { mediaType, tomoName, element } = data;

        // Check media status
        fetch(`/media_status/${mediaType}/${tomoName}`)
            .then(response => response.json())
            .then(statusData => {
                if (statusData.status === 'ready') {
                    updateMedia(key, mediaType, tomoName);
                } else {
                    // Increment attempt counter
                    data.attempts++;
                    logDebug(`${mediaType} for ${tomoName} not ready: ${statusData.status} (attempt ${data.attempts}/${MAX_RETRIES})`);

                    // Show status message on element
                    if (element.tagName === 'IMG') {
                        element.setAttribute('title', `Status: ${statusData.status} (${data.attempts}/${MAX_RETRIES})`);
                    }

                    // Remove from monitoring if max attempts reached
                    if (data.attempts >= MAX_RETRIES) {
                        logDebug(`Giving up on ${mediaType} for ${tomoName} after ${MAX_RETRIES} attempts`);
                    }
                }
            })
            .catch(error => {
                console.error(`Error checking ${mediaType} status for ${tomoName}:`, error);
            });
    }
}

/**
 * Update thumbnail when it becomes available
 */
function updateThumbnail(tomoName, thumbnailPath) {
    const data = monitoredMedia.thumbnails.get(tomoName);
    if (!data) return;

    const { element } = data;

    // Find the containing div that might have a placeholder message
    const placeholderContainer = element.closest('.placeholder');
    const thumbnailContainer = element.closest('.thumbnail-container');

    // Create a new image with proper styling
    const newImage = new Image();
    newImage.onload = () => {
        logDebug(`Thumbnail for ${tomoName} loaded successfully`);

        // Apply the same styling as regular thumbnails
        newImage.className = element.className || '';
        newImage.style.width = '100%';
        newImage.style.height = '100%';
        newImage.style.objectFit = 'contain';
        newImage.alt = `${tomoName} thumbnail`;

        // Replace placeholder with the actual thumbnail
        if (placeholderContainer) {
            // Clear the placeholder container and add the new image
            placeholderContainer.innerHTML = '';
            placeholderContainer.appendChild(newImage);
            // Remove the placeholder class if it exists
            placeholderContainer.classList.remove('placeholder');
        } else if (thumbnailContainer) {
            // Replace the existing image with the new one
            element.parentNode.replaceChild(newImage, element);
        } else {
            // Just replace the element directly
            element.parentNode.replaceChild(newImage, element);
        }

        // Remove from monitoring
        monitoredMedia.thumbnails.delete(tomoName);
    };

    newImage.onerror = () => {
        logDebug(`Failed to load thumbnail for ${tomoName}, will retry`);
        // Keep in monitoring, but don't increment attempts here
    };

    // Update the image source with cache-busting
    const timestamp = new Date().getTime();
    newImage.src = `/thumbnails/${thumbnailPath}?t=${timestamp}`;
}

/**
 * Update media when it becomes available
 */
function updateMedia(key, mediaType, tomoName) {
    const data = monitoredMedia.media.get(key);
    if (!data) return;

    const { element } = data;

    // Update the image/video source with cache-busting
    const timestamp = new Date().getTime();
    const mediaUrl = `/serve_media/${mediaType}/${tomoName}?t=${timestamp}`;

    if (element.tagName === 'IMG') {
        // For image elements
        element.src = mediaUrl;

        // Add loading and error handling
        element.onload = () => {
            logDebug(`${mediaType} for ${tomoName} loaded successfully`);
            // Remove from monitoring
            monitoredMedia.media.delete(key);
        };

        element.onerror = () => {
            logDebug(`Failed to load ${mediaType} for ${tomoName}, will retry`);
            // Keep in monitoring, but don't increment attempts here
        };
    } else if (element.tagName === 'DIV') {
        // For container elements, create an appropriate media element
        element.innerHTML = '';

        if (mediaType === 'tiltseries' || mediaType === 'tomogram') {
            // Use interactive GIF player for animations
            initGifPlayer(element, mediaUrl, mediaType, tomoName, key);
        } else {
            // Create plain image for lowmag
            const mediaElement = document.createElement('img');
            mediaElement.src = mediaUrl;
            mediaElement.className = 'img-fluid';
            mediaElement.alt = `${tomoName} low magnification image`;
            element.appendChild(mediaElement);

            mediaElement.onload = () => {
                logDebug(`${mediaType} for ${tomoName} loaded successfully`);
                monitoredMedia.media.delete(key);
            };
            mediaElement.onerror = () => {
                logDebug(`Failed to load ${mediaType} for ${tomoName}, will retry`);
            };
        }
    }
}

/**
 * Interactive GIF player with play/pause and frame scrubbing.
 * Requires omggif (GifReader) to be available as a global.
 */
function initGifPlayer(container, gifUrl, mediaType, tomoName, monitorKey) {
    if (typeof GifReader === 'undefined') {
        // omggif not loaded yet — fall back to plain animated gif
        logDebug('omggif not available, falling back to plain <img> for ' + tomoName);
        const img = document.createElement('img');
        img.src = gifUrl;
        img.className = 'img-fluid';
        img.alt = `${tomoName} ${mediaType} animation`;
        container.appendChild(img);
        img.onload = () => monitoredMedia.media.delete(monitorKey);
        return;
    }

    fetch(gifUrl)
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.arrayBuffer();
        })
        .then(buf => {
            const bytes = new Uint8Array(buf);
            const reader = new GifReader(bytes);
            const numFrames = reader.numFrames();
            const W = reader.width;
            const H = reader.height;

            // Decoded frame cache
            const frameCache = [];

            function getFrame(idx) {
                if (!frameCache[idx]) {
                    const pixels = new Uint8ClampedArray(W * H * 4);
                    reader.decodeAndBlitFrameRGBA(idx, pixels);
                    frameCache[idx] = new ImageData(pixels, W, H);
                }
                return frameCache[idx];
            }

            // Canvas
            const canvas = document.createElement('canvas');
            canvas.width = W;
            canvas.height = H;
            canvas.style.cssText = 'max-width:100%;max-height:260px;display:block;margin:0 auto;';
            const ctx = canvas.getContext('2d');

            // Controls bar
            const controls = document.createElement('div');
            controls.className = 'gif-player-controls';

            const btn = document.createElement('button');
            btn.className = 'btn btn-sm btn-outline-secondary';
            btn.title = 'Play / Pause';
            btn.textContent = '\u23F8'; // ⏸

            const slider = document.createElement('input');
            slider.type = 'range';
            slider.min = 0;
            slider.max = numFrames - 1;
            slider.value = 0;

            const frameLabel = document.createElement('small');
            frameLabel.className = 'text-muted text-nowrap';
            frameLabel.textContent = `1 / ${numFrames}`;

            controls.append(btn, slider, frameLabel);
            container.append(canvas, controls);

            // Render first frame immediately
            ctx.putImageData(getFrame(0), 0, 0);

            // Playback state
            let currentFrame = 0;
            let playing = true;
            let rafId = null;
            let lastTime = 0;

            function getDelay(idx) {
                const fi = reader.frameInfo(idx);
                // GIF delay is in centiseconds; 0 means "as fast as possible" → use 100ms
                return (fi.delay > 0 ? fi.delay : 10) * 10;
            }

            function animStep(ts) {
                if (!playing) return;
                if (ts - lastTime >= getDelay(currentFrame)) {
                    currentFrame = (currentFrame + 1) % numFrames;
                    ctx.putImageData(getFrame(currentFrame), 0, 0);
                    slider.value = currentFrame;
                    frameLabel.textContent = `${currentFrame + 1} / ${numFrames}`;
                    lastTime = ts;
                }
                rafId = requestAnimationFrame(animStep);
            }

            rafId = requestAnimationFrame(animStep);

            btn.addEventListener('click', () => {
                playing = !playing;
                btn.textContent = playing ? '\u23F8' : '\u25B6'; // ⏸ or ▶
                if (playing) {
                    lastTime = 0;
                    rafId = requestAnimationFrame(animStep);
                } else {
                    cancelAnimationFrame(rafId);
                }
            });

            slider.addEventListener('input', () => {
                currentFrame = parseInt(slider.value);
                frameLabel.textContent = `${currentFrame + 1} / ${numFrames}`;
                ctx.putImageData(getFrame(currentFrame), 0, 0);
            });

            // Hide loading spinner if present
            const loadingEl = document.getElementById(`${mediaType}-loading`);
            if (loadingEl) loadingEl.style.display = 'none';

            monitoredMedia.media.delete(monitorKey);
            logDebug(`GIF player ready for ${mediaType} ${tomoName}: ${numFrames} frames`);
        })
        .catch(err => {
            console.error(`[MediaUpdater] GIF player error for ${tomoName} ${mediaType}:`, err);
            // Retry will happen on next poll cycle — element already cleared so show message
            container.innerHTML = '<div class="text-center text-muted small p-2">Loading animation...</div>';
        });
}

/**
 * Debug logging helper
 */
function logDebug(message) {
    if (DEBUG) {
        console.log(`[MediaUpdater] ${message}`);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initMediaUpdater);