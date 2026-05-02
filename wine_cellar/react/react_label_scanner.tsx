import React, { useState, useRef, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import { CameraError, CameraErrorType } from './components/CameraError';
import ErrorBoundary from './components/ErrorBoundary';

// Compression settings
const MAX_DIMENSION = 2048; // Max width or height in pixels
const JPEG_QUALITY = 0.85; // 85% quality

const translated = {
    captureButton: 'Capture Photo',
    retakeButton: 'Retake',
    usePhotoButton: 'Use This Photo',
    nextPhotoButton: 'Next Photo',
    submitAllButton: 'Process All Images',
    instructionsBarcode: '1/3: Position the barcode in the frame and tap to capture',
    instructionsBack: '2/3: Position the back label in the frame and tap to capture',
    instructionsFront: '3/3: Position the front label in the frame and tap to capture',
};

const LabelScanner: React.FC = () => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [stream, setStream] = useState<MediaStream | null>(null);
    const [capturedImages, setCapturedImages] = useState<string[]>([]);
    const [currentStep, setCurrentStep] = useState<number>(0); // 0=barcode, 1=front, 2=back
    const [currentCapture, setCurrentCapture] = useState<string | null>(null);
    const [cameraError, setCameraError] = useState<CameraErrorType>(null);
    const [retryKey, setRetryKey] = useState(0);

    const stepInstructions = [
        translated.instructionsBarcode,
        translated.instructionsBack,
        translated.instructionsFront,
    ];

    const startCamera = useCallback(async () => {
        // Check if we're on HTTPS or localhost
        if (!window.isSecureContext) {
            setCameraError('https');
            return;
        }

        try {
            const mediaStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }, // Use back camera on mobile
                audio: false,
            });

            setStream(mediaStream);
            if (videoRef.current) {
                videoRef.current.srcObject = mediaStream;
            }
            setCameraError(null);
        } catch (error) {
            console.error('Camera error:', error);
            if (error instanceof Error) {
                const errorName = error.name;
                const errorMessage = error.message.toLowerCase();

                if (errorName === 'NotAllowedError' || errorMessage.includes('permission')) {
                    setCameraError('permission');
                } else if (errorName === 'NotFoundError' || errorMessage.includes('not found')) {
                    setCameraError('notfound');
                } else if (!window.isSecureContext) {
                    setCameraError('https');
                } else {
                    setCameraError('unknown');
                }
            } else {
                setCameraError('unknown');
            }
        }
    }, []);

    React.useEffect(() => {
        startCamera();

        return () => {
            if (stream) {
                stream.getTracks().forEach((track) => track.stop());
            }
        };
    }, [retryKey]);

    const capturePhoto = () => {
        if (videoRef.current && canvasRef.current) {
            const video = videoRef.current;
            const canvas = canvasRef.current;
            const context = canvas.getContext('2d');

            if (context) {
                // Calculate dimensions, scaling down if necessary
                let width = video.videoWidth;
                let height = video.videoHeight;

                if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
                    if (width > height) {
                        height = Math.round((height * MAX_DIMENSION) / width);
                        width = MAX_DIMENSION;
                    } else {
                        width = Math.round((width * MAX_DIMENSION) / height);
                        height = MAX_DIMENSION;
                    }
                }

                canvas.width = width;
                canvas.height = height;

                // Use high-quality image smoothing for better downscaling
                context.imageSmoothingEnabled = true;
                context.imageSmoothingQuality = 'high';
                context.drawImage(video, 0, 0, width, height);

                const imageDataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY);
                setCurrentCapture(imageDataUrl);

                // Stop the camera stream temporarily
                if (stream) {
                    stream.getTracks().forEach((track) => track.stop());
                }
            }
        }
    };

    const retakePhoto = () => {
        setCurrentCapture(null);
        setRetryKey((prev) => prev + 1);
    };

    const nextPhoto = () => {
        if (currentCapture) {
            // Save current capture
            setCapturedImages((prev) => [...prev, currentCapture]);
            setCurrentCapture(null);
            setCurrentStep((prev) => prev + 1);
            setRetryKey((prev) => prev + 1);
        }
    };

    const submitAllImages = () => {
        const allImages = [...capturedImages, currentCapture].filter((img): img is string => Boolean(img));
        if (allImages.length > 0) {
            // Create a form and submit all images
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = window.location.href;

            const csrfToken = document.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]');
            if (csrfToken) {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrfmiddlewaretoken';
                csrfInput.value = csrfToken.value;
                form.appendChild(csrfInput);
            }

            // Add all images as separate fields
            allImages.forEach((img, idx) => {
                const imageInput = document.createElement('input');
                imageInput.type = 'hidden';
                imageInput.name = `image_data_${idx}`;
                imageInput.value = img;
                form.appendChild(imageInput);
            });

            // Add image count
            const countInput = document.createElement('input');
            countInput.type = 'hidden';
            countInput.name = 'image_count';
            countInput.value = allImages.length.toString();
            form.appendChild(countInput);

            document.body.appendChild(form);
            form.submit();
        }
    };

    const handleRetry = () => {
        setCameraError(null);
        setRetryKey((prev) => prev + 1);
    };

    if (cameraError) {
        return <CameraError errorType={cameraError} onRetry={handleRetry} />;
    }

    return (
        <div className="label-scanner">
            <p className="form-hint mb-12">{stepInstructions[currentStep]}</p>
            
            <div className="label-scanner__viewport">
                {!currentCapture ? (
                    <>
                        <video
                            ref={videoRef}
                            autoPlay
                            playsInline
                            className="label-scanner__video"
                        />
                        <div className="overlay">
                            <div className="overlay-element top-left" />
                            <div className="overlay-element top-right" />
                            <div className="overlay-element bottom-left" />
                            <div className="overlay-element bottom-right" />
                        </div>
                    </>
                ) : (
                    <img src={currentCapture} alt="Captured" className="label-scanner__preview" />
                )}
            </div>

            <canvas ref={canvasRef} style={{ display: 'none' }} />

            {/* Show thumbnails of captured images */}
            {capturedImages.length > 0 && (
                <div className="label-scanner__thumbnails">
                    {capturedImages.map((img, idx) => (
                        <img
                            key={idx}
                            src={img}
                            alt={`Captured ${idx + 1}`}
                            className="label-scanner__thumbnail"
                        />
                    ))}
                </div>
            )}

            <div className="label-scanner__controls">
                {!currentCapture ? (
                    <button
                        type="button"
                        className="pure-button button__secondary"
                        onClick={capturePhoto}
                        aria-label={`${translated.captureButton}. ${stepInstructions[currentStep]}`}
                    >
                        {translated.captureButton}
                    </button>
                ) : (
                    <>
                        <button
                            type="button"
                            className="pure-button button__tertiary"
                            onClick={retakePhoto}
                            aria-label={translated.retakeButton}
                        >
                            {translated.retakeButton}
                        </button>
                        {currentStep < stepInstructions.length - 1 ? (
                            <button
                                type="button"
                                className="pure-button button__secondary"
                                onClick={nextPhoto}
                                aria-label={translated.nextPhotoButton}
                            >
                                {translated.nextPhotoButton}
                            </button>
                        ) : (
                            <button
                                type="button"
                                className="pure-button button__secondary"
                                onClick={submitAllImages}
                                aria-label={translated.submitAllButton}
                            >
                                {translated.submitAllButton}
                            </button>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

const initLabelScanner = () => {
    const container = document.getElementById('label-scanner');
    if (container) {
        const root = createRoot(container);
        root.render(<ErrorBoundary><LabelScanner /></ErrorBoundary>);
    }
};

document.addEventListener('DOMContentLoaded', initLabelScanner, false);
