document.addEventListener('DOMContentLoaded', function() {
    // Add any client-side functionality needed
    console.log('Application loaded');
    
    // Example: Confirm before stopping a process
    document.querySelectorAll('.btn-danger').forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to stop this process?')) {
                e.preventDefault();
            }
        });
    });
    
    // Example: Auto-scroll logs to bottom
    const logContainer = document.querySelector('.log-container');
    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
});
