document.addEventListener("DOMContentLoaded", function() {
    // Fade out effect for page transitions
    document.body.classList.add('fade-out');

    window.addEventListener('beforeunload', function() {
        document.body.classList.add('fade-in');
    });

    // Add fade-in class to body
    document.body.classList.add('fade-in');
});
