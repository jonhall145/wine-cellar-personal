import React, { useState, useRef, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
// @ts-ignore
import django from 'django';

const translated = {
    captureButton: django.gettext('Capture Photo'),
    retakeButton: django.gettext('Retake'),
    usePhotoButton: django.gettext('Use This Photo'),
    cameraError: django.gettext('Camera access denied'),
    cameraErrorHint: django.gettext('Please allow camera access in your browser settings.'),
    httpsRequired: django.gettext('HTTPS required'),
    httpsRequiredHint: django.gettext('Camera access requires HTTPS.'),
    noCameraFound: django.gettext('No camera found'),
    noCameraFoundHint: django.gettext('No camera detected on this device.'),
    unknownError: django.gettext('Scanner error'),
    unknownErrorHint: django.gettext('An error occurred while accessing the camera.'),
    retryButton: django.gettext('Try Again'),
    instructions: django.gettext('Position the wine label in the frame and tap to capture'),
};

interface CameraErrorProps {
    errorType: 'permission' | 'https' | 'notfound' | 'unknown';
    onRetry: () => void;
}

const CameraError: React.FC<CameraErrorProps> = ({ errorType, onRetry }) => {
    let title = translated.unknownError;
    let message = translated.unknownErrorHint;

    if (errorType === 'permission') {
        title = translated.cameraError;
        message = translated.cameraErrorHint;
    } else if (errorType === 'https') {
        title = translated.httpsRequired;
        message = translated.httpsRequiredHint;
    } else if (errorType === 'notfound') {
        title = translated.noCameraFound;
        message = translated.noCameraFoundHint;
    }

    return (
        <div className="camera-error">
            <div className="camera-error__icon">⚠️</div>
            <h3 className="camera-error__title">{title}</h3>
            <p className="camera-error__message">{message}</p>
            {errorType !== 'https' && (
                <button className="camera-error__retry" onClick={onRetry}>
                    {translated.retryButton}
                </button>
            )}
        </div>
    );
};

const LabelScanner: React.FC = () => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [stream, setStream] = useState<MediaStream | null>(null);
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [cameraError, setCameraError] = useState<'permission' | 'https' | 'notfound' | 'unknown' | null>(null);
    const [retryKey, setRetryKey] = useState(0);

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
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                context.drawImage(video, 0, 0);

                const imageDataUrl = canvas.toDataURL('image/jpeg', 0.9);
                setCapturedImage(imageDataUrl);

                // Stop the camera stream
                if (stream) {
                    stream.getTracks().forEach((track) => track.stop());
                }
            }
        }
    };

    const retakePhoto = () => {
        setCapturedImage(null);
        setRetryKey((prev) => prev + 1);
    };

    const usePhoto = () => {
        if (capturedImage) {
            // Create a form and submit the image
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

            const imageInput = document.createElement('input');
            imageInput.type = 'hidden';
            imageInput.name = 'image_data';
            imageInput.value = capturedImage;
            form.appendChild(imageInput);

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
            <p className="form-hint mb-12">{translated.instructions}</p>
            
            <div className="label-scanner__viewport">
                {!capturedImage ? (
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
                    <img src={capturedImage} alt="Captured" className="label-scanner__preview" />
                )}
            </div>

            <canvas ref={canvasRef} style={{ display: 'none' }} />

            <div className="label-scanner__controls">
                {!capturedImage ? (
                    <button
                        type="button"
                        className="pure-button button__secondary"
                        onClick={capturePhoto}
                    >
                        {translated.captureButton}
                    </button>
                ) : (
                    <>
                        <button
                            type="button"
                            className="pure-button button__tertiary"
                            onClick={retakePhoto}
                        >
                            {translated.retakeButton}
                        </button>
                        <button
                            type="button"
                            className="pure-button button__secondary"
                            onClick={usePhoto}
                        >
                            {translated.usePhotoButton}
                        </button>
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
        root.render(<LabelScanner />);
    }
};

document.addEventListener('DOMContentLoaded', initLabelScanner, false);
