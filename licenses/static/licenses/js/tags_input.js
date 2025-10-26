/**
 * Tags Input Widget JavaScript
 * 
 * Provides interactive functionality for the tags input widget,
 * including real-time preview and validation.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all tags input widgets
    const tagsInputs = document.querySelectorAll('input.tags-input');
    
    tagsInputs.forEach(function(input) {
        initializeTagsInput(input);
    });
});

function initializeTagsInput(input) {
    const container = input.closest('.tags-input-container');
    const preview = container.querySelector('.tags-preview');
    const maxTags = 4;
    
    // Create preview container if it doesn't exist
    if (!preview) {
        const previewDiv = document.createElement('div');
        previewDiv.className = 'tags-preview';
        previewDiv.id = 'tags-preview-' + input.id;
        container.appendChild(previewDiv);
    }
    
    // Update preview on input change
    function updatePreview() {
        let value = input.value.trim();
        
        // Handle "null", "None", or empty values
        if (value === 'null' || value === 'None' || value === '') {
            value = '';
            input.value = ''; // Clear the input if it shows "null"
        }
        
        const tags = value ? value.split(',').map(tag => tag.trim()).filter(tag => tag) : [];
        
        // Clear existing preview
        preview.innerHTML = '';
        
        // Display tags
        tags.forEach((tag, index) => {
            if (index >= maxTags) return; // Don't show more than max tags
            
            const tagElement = document.createElement('span');
            tagElement.className = 'tag-item';
            
            // Add warning class if over limit
            if (index >= maxTags - 1 && tags.length > maxTags) {
                tagElement.classList.add('over-limit');
            }
            
            tagElement.innerHTML = tag + '<span class="tag-remove" onclick="removeTag(this)">&times;</span>';
            preview.appendChild(tagElement);
        });
        
        // Show warning if over limit
        if (tags.length > maxTags) {
            const warning = document.createElement('div');
            warning.className = 'tag-warning';
            warning.style.color = '#c62828';
            warning.style.fontSize = '12px';
            warning.style.marginTop = '4px';
            warning.textContent = `Maximum ${maxTags} tags allowed. Showing first ${maxTags} tags.`;
            preview.appendChild(warning);
        }
    }
    
    // Handle input events
    input.addEventListener('input', updatePreview);
    input.addEventListener('paste', function() {
        setTimeout(updatePreview, 10); // Delay to allow paste to complete
    });
    
    // Initial update
    updatePreview();
    
    // Auto-complete on comma
    input.addEventListener('keydown', function(e) {
        if (e.key === ',' || e.key === 'Enter') {
            e.preventDefault();
            const cursorPos = input.selectionStart;
            const value = input.value;
            
            // Insert comma if not already present
            if (e.key === ',' && value[cursorPos - 1] !== ',') {
                input.value = value.slice(0, cursorPos) + ', ' + value.slice(cursorPos);
                input.setSelectionRange(cursorPos + 2, cursorPos + 2);
            }
            
            updatePreview();
        }
    });
}

// Global function to remove tags
function removeTag(element) {
    const tagElement = element.closest('.tag-item');
    const tagText = tagElement.textContent.replace('×', '').trim();
    
    // Find the input field
    const container = tagElement.closest('.tags-input-container');
    const input = container.querySelector('input.tags-input');
    
    // Remove the tag from input
    const currentValue = input.value;
    const tags = currentValue.split(',').map(tag => tag.trim()).filter(tag => tag);
    const newTags = tags.filter(tag => tag !== tagText);
    
    input.value = newTags.join(', ');
    
    // Update preview
    const preview = container.querySelector('.tags-preview');
    preview.innerHTML = '';
    
    newTags.forEach((tag, index) => {
        const tagElement = document.createElement('span');
        tagElement.className = 'tag-item';
        tagElement.innerHTML = tag + '<span class="tag-remove" onclick="removeTag(this)">&times;</span>';
        preview.appendChild(tagElement);
    });
}
