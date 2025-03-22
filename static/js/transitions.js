document.addEventListener("DOMContentLoaded", function() {
    // Fade out effect for page transitions
    document.body.classList.add('fade-out');

    window.addEventListener('beforeunload', function() {
        document.body.classList.add('fade-in');
    });

    // Add fade-in class to body
    document.body.classList.add('fade-in');

    // Create buttons for events
    document.querySelectorAll(".day").forEach(day => {
        const events = day.getAttribute("data-events");
        if (events) {
            const eventList = JSON.parse(events);
            eventList.forEach(event => {
                const button = document.createElement("button");
                button.classList.add("event-button");
                button.setAttribute("data-details", event.details);
                button.innerText = event.title;
                day.appendChild(button);
            });
        }
    });

    // Event listener for event buttons
    document.querySelectorAll(".event-button").forEach(button => {
        button.addEventListener("click", function() {
            const eventModal = document.getElementById("eventModal");
            const eventDetails = document.getElementById("eventDetails");
            eventModal.style.display = "block";
            eventDetails.innerText = this.getAttribute("data-details");
        });
    });
});
