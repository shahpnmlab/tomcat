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
    // The URL is now constructed with the new route, thumbnailPath is tomoName
    newImage.src = `/thumbnail/${thumbnailPath}?t=${timestamp}`;
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
        let mediaElement;

        if (mediaType === 'lowmag') {
            // Create image for lowmag
            mediaElement = document.createElement('img');
            mediaElement.src = mediaUrl;
            mediaElement.className = 'img-fluid';
            mediaElement.alt = `${tomoName} low magnification image`;
        } else {
            // Create image for animations
            mediaElement = document.createElement('img');
            mediaElement.src = mediaUrl;
            mediaElement.className = 'img-fluid';
            mediaElement.alt = `${tomoName} ${mediaType} animation`;
        }

        // Clear the container and add the new element
        element.innerHTML = '';
        element.appendChild(mediaElement);

        // Add loading and error handling
        mediaElement.onload = () => {
            logDebug(`${mediaType} for ${tomoName} loaded successfully`);
            // Remove from monitoring
            monitoredMedia.media.delete(key);
        };

        mediaElement.onerror = () => {
            logDebug(`Failed to load ${mediaType} for ${tomoName}, will retry`);
            // Keep in monitoring but don't increment attempts here
        };
    }
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