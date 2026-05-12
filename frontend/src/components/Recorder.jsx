import React, { useEffect, useRef, useState } from "react";

function pickMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];
  for (const t of candidates) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(t)) return t;
  }
  return "";
}

export default function Recorder({ onStop, onStart, disabled }) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const mimeTypeRef = useRef("");
  const beepTimerRef = useRef(null);

  function playBeep(frequency = 1000, duration = 0.2, volume = 0.4) {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioContext();
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);

      oscillator.frequency.value = frequency;
      oscillator.type = "sine";

      gainNode.gain.setValueAtTime(volume, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);

      oscillator.start(ctx.currentTime);
      oscillator.stop(ctx.currentTime + duration);
    } catch (e) {
      console.error("Failed to play beep:", e);
    }
  }

  useEffect(() => {
    return () => {
      // Cleanup on unmount.
      tryStop();
      if (beepTimerRef.current) {
        clearTimeout(beepTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function tryStop() {
    try {
      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state !== "inactive"
      ) {
        mediaRecorderRef.current.stop();
      }
    } catch (_) {}

    const stream = streamRef.current;
    if (stream) {
      for (const tr of stream.getTracks()) tr.stop();
    }
    streamRef.current = null;

    const ctx = audioContextRef.current;
    if (ctx) ctx.close().catch(() => {});
    audioContextRef.current = null;

    mediaRecorderRef.current = null;
    chunksRef.current = [];
  }

  function cleanupAfterStop() {
    // Release mic promptly (after MediaRecorder has finalized chunks).
    const stream = streamRef.current;
    if (stream) {
      for (const tr of stream.getTracks()) tr.stop();
    }
    streamRef.current = null;

    const ctx = audioContextRef.current;
    if (ctx) ctx.close().catch(() => {});
    audioContextRef.current = null;

    mediaRecorderRef.current = null;
    chunksRef.current = [];
  }

  async function start() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Audio recording not supported in this browser.");
      return;
    }

    try {
      const mimeType = pickMimeType();
      mimeTypeRef.current = mimeType;
      chunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      onStart?.();

      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };
      
      recorder.onerror = (e) => {
        console.error("MediaRecorder error:", e);
        setError("Recording failed. Please try again.");
      };
      
      recorder.onstop = () => {
        if (beepTimerRef.current) {
          clearTimeout(beepTimerRef.current);
        }
        
        const type = mimeTypeRef.current || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        
        // Check for empty or extremely small blobs (less than 1KB is likely just header)
        if (blob.size < 1024) {
          setError("No voice detected. Please speak into the microphone.");
        } else {
          onStop?.(blob);
        }
        cleanupAfterStop();
      };

      // Schedule beep after 2 seconds
      beepTimerRef.current = setTimeout(() => {
        playBeep();
      }, 2000);

      recorder.start(200); // Collect data every 200ms to avoid data loss
      setRecording(true);
    } catch (err) {
      console.error("Failed to start recording:", err);
      if (err.name === "NotAllowedError") {
        setError("Microphone access denied. Please allow microphone permissions.");
      } else {
        setError("Could not access microphone. Please ensure it is connected.");
      }
    }
  }

  function stop() {
    if (!mediaRecorderRef.current) return;
    setRecording(false);
    try {
      mediaRecorderRef.current.stop();
    } catch (_) {}
  }

  return (
    <div className="status">
      <button
        className="primary"
        onClick={start}
        disabled={disabled || recording}
      >
        {recording ? "Recording..." : "Start Recording"}
      </button>{" "}
      <button onClick={stop} disabled={disabled || !recording}>
        Stop
      </button>
      {error ? (
        <div style={{ marginTop: 8, color: "#ea4335" }}>{error}</div>
      ) : null}
    </div>
  );
}
