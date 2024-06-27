// Function to poll the server for the latest weight data
function pollWeightData() {
    fetch('/get_weight')
        .then(response => response.json())
        .then(data => {
            if (data.weight !== null) {
                document.getElementById('weightDisplay').innerText = `Weight: ${data.weight} kg`; // Corrected line with backticks for interpolation
                document.getElementById('saveButtonDiv').style.display = 'block'; // Show save button
            } else {
                setTimeout(pollWeightData, 1000); // Retry after 1 second if no weight data
            }
        })
        .catch(error => {
            console.error('Error fetching weight data:', error);
            setTimeout(pollWeightData, 1000); // Retry after 1 second in case of error
        });
}

// Start polling when the page is loaded
window.onload = function() {
    pollWeightData();
};

// Function to handle saving history
document.getElementById('saveButton').addEventListener('click', function() {
    fetch('/save_history', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log(data);
        alert('History saved successfully!');
        document.getElementById('saveButtonDiv').style.display = 'none'; // Hide save button after saving
    })  
    .catch(error => {
        console.error('Error:', error);
        alert('Sampah sukses disimpan.');
    });
});
