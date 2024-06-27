from inference_sdk import InferenceHTTPClient, InferenceConfiguration

# Set custom configuration with confidence threshold
custom_configuration = InferenceConfiguration(confidence_threshold=0.3)

# Initialize the InferenceHTTPClient
CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key="nXHlQP10OlbsjZEzF2Re"
)

# Use the custom configuration for inference
with CLIENT.use_configuration(custom_configuration):
    # Perform inference
    result = CLIENT.infer('trash.jpeg', model_id="trash-detection-otdmj/35")

# Extract relevant information from the result and format it for user readability
if 'predictions' in result:
    predictions = result['predictions']
    num_trash_detected = len(predictions)
    if num_trash_detected > 0:
        for prediction in predictions:
            trash_type = prediction['class']
            confidence = prediction['confidence']
            x_coord = prediction['x']
            y_coord = prediction['y']
            print(f"{num_trash_detected} trash detected, trash type is: {trash_type}, confidence: {confidence}, coordinates: ({x_coord}, {y_coord})")
    else:
        print("No trash detected in the image.")
else:
    print("No predictions found in the result.")
