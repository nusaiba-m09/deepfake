# NeuralForensics NSU // Cyber Lab

Presentation-ready deepfake detection interface built in plain HTML5, CSS3, and vanilla JavaScript, backed by a local PyTorch Meso4 detector.

## Run locally

1. Start the integrated web and inference server from the project root:

```bash
python3 detector_server.py
```

2. Open `http://localhost:8080` in a modern browser.
3. Drop or select an MP4 to analyze it automatically, or click **Authorize Camera Feed** before using live capture.
4. Click **Initiate Threat Analysis** to repeat the analysis for the currently selected source.

The camera does not start on page load. It remains off until the authorization button is clicked and browser permission is granted.

## Detection

Uploaded videos are sampled across 12 frames and evaluated locally. The interface reports a deepfake verdict when the mean synthetic probability is above `0.50`. No external API credentials or internet connection are required during analysis.

The interface provides two selectable engines:

- `Detection Model 1` runs with the bundled project model.
- `Detection Model 2` uses an optional server-side video detection service. Create a trial API token and set it before starting the server:

```bash
export HIVE_API_KEY="your-token"
python3 detector_server.py
```

The token is never sent to or stored by the browser. If it is absent, Model 2 returns a configuration error instead of generating a simulated verdict.

## Fetch stage-ready test media

Run the utility below from the project root to create `NSU_Demo_Videos` and download sample MP4 files:

```bash
python fetch_test_media.py
```

The script prints a terminal-style acquisition log while it creates the folder and downloads the files.

Any MP4 files already placed in `NSU_Demo_Videos` can be dragged directly onto the detection surface.

The three bundled known-synthetic videos are also available through the website's **Verification Samples** controls. Selecting one loads it into the standard MP4 analysis workflow; click **Run MP4 Deepfake Analysis** to test the chosen model.
