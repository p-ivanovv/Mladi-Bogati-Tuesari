document.querySelectorAll(".event-button").forEach(button => {
    button.addEventListener("click", function() {
        eventModal.style.display = "block";
        eventDetails.innerText = this.getAttribute("data-details");
    });
});
