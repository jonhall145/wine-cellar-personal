import React, { useState, useEffect, useRef, useCallback } from 'react'
import { createRoot } from 'react-dom/client'
import { BarcodeScanner, DetectedBarcode } from 'react-barcode-scanner'
// @ts-ignore
import django from 'django'

import { BarcodeDetector, prepareZXingModule } from 'barcode-detector/ponyfill'

const translated = {
  advanced: django.gettext('Advanced'),
  helptext: django.gettext(
    "Choose the type of barcode you want to scan, sometimes this can help if scanning doesn't work."
  ),
  cameraError: django.gettext('Camera access denied'),
  cameraErrorHint: django.gettext(
    'Please allow camera access in your browser settings, or ensure you are using HTTPS.'
  ),
  httpsRequired: django.gettext('HTTPS required'),
  httpsRequiredHint: django.gettext(
    'Camera access requires a secure connection (HTTPS). Please access this page via HTTPS.'
  ),
  noCameraFound: django.gettext('No camera found'),
  noCameraFoundHint: django.gettext(
    'No camera was detected on this device. Please ensure a camera is connected.'
  ),
  unknownError: django.gettext('Scanner error'),
  unknownErrorHint: django.gettext(
    'An error occurred while accessing the camera. Please try again.'
  ),
  retryButton: django.gettext('Try Again'),
  captureButton: django.gettext('Capture & Analyze'),
  analyzing: django.gettext('Analyzing...'),
  noBarcodeFound: django.gettext('No barcode found in image'),
}

type CameraErrorType = 'permission' | 'https' | 'notfound' | 'unknown' | null

const CameraError = ({ errorType, onRetry }: { errorType: CameraErrorType; onRetry: () => void }) => {
  let title = translated.unknownError
  let message = translated.unknownErrorHint

  if (errorType === 'permission') {
    title = translated.cameraError
    message = translated.cameraErrorHint
  } else if (errorType === 'https') {
    title = translated.httpsRequired
    message = translated.httpsRequiredHint
  } else if (errorType === 'notfound') {
    title = translated.noCameraFound
    message = translated.noCameraFoundHint
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
  )
}

const Scanner = () => {
  const [selectedFormat, setSelectedFormat] = useState('any')
  const [cameraError, setCameraError] = useState<CameraErrorType>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const scannerRef = useRef<HTMLDivElement>(null)
  const defaultFormats = ['ean_13', 'ean_8', 'upc_a', 'code_39', 'itf']

  useEffect(() => {
    // Check if we're on HTTPS or localhost
    const isSecureContext = window.isSecureContext
    if (!isSecureContext) {
      setCameraError('https')
    }
  }, [])

  const handleCapture = (barcodes: DetectedBarcode[]) => {
    if (barcodes.length > 0) {
      window.location.href = '/wine/scan/' + barcodes[0].rawValue
    }
  }

  const handleError = (error: unknown) => {
    console.error('Camera error:', error)
    
    if (error instanceof Error) {
      const errorName = error.name
      const errorMessage = error.message.toLowerCase()

      if (errorName === 'NotAllowedError' || errorMessage.includes('permission')) {
        setCameraError('permission')
      } else if (errorName === 'NotFoundError' || errorMessage.includes('not found')) {
        setCameraError('notfound')
      } else if (errorName === 'NotReadableError' || errorMessage.includes('could not start')) {
        setCameraError('unknown')
      } else if (!window.isSecureContext) {
        setCameraError('https')
      } else {
        setCameraError('unknown')
      }
    } else {
      setCameraError('unknown')
    }
  }

  const handleRetry = () => {
    setCameraError(null)
    setRetryKey((prev) => prev + 1)
  }

  const captureAndAnalyze = useCallback(async () => {
    if (!scannerRef.current) return
    
    // Find the video element within the scanner
    const video = scannerRef.current.querySelector('video')
    if (!video || video.videoWidth === 0) {
      setAnalyzeError('Camera not ready')
      return
    }

    setIsAnalyzing(true)
    setAnalyzeError(null)

    try {
      // Create a canvas and draw the current video frame
      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        throw new Error('Could not get canvas context')
      }
      ctx.drawImage(video, 0, 0)

      // Convert to base64
      const imageData = canvas.toDataURL('image/png')

      // Get CSRF token
      const csrfToken = document.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]')?.value
        || document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content
        || ''

      // Send to server for analysis
      const response = await fetch('/wine/scan-barcode/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ image: imageData }),
      })

      const result = await response.json()

      if (result.success && result.barcode) {
        // Barcode found - redirect to scanned wine page
        window.location.href = '/wine/scan/' + result.barcode
      } else {
        setAnalyzeError(translated.noBarcodeFound)
      }
    } catch (error) {
      console.error('Error analyzing image:', error)
      setAnalyzeError(error instanceof Error ? error.message : 'Analysis failed')
    } finally {
      setIsAnalyzing(false)
    }
  }, [])

  if (cameraError) {
    return <CameraError errorType={cameraError} onRetry={handleRetry} />
  }

  return (
    <>
      <section className="form__scanner__details">
        <details>
          <summary>{translated.advanced}</summary>
          <p className="form-hint">{translated.helptext}</p>
          <select
            value={selectedFormat}
            onChange={(e) => setSelectedFormat(e.target.value)}
          >
            <option value="">{django.gettext('All')}</option>
            <option value="code_39">Code 39</option>
            <option value="code_93">Code 93</option>
            <option value="code_128">Code 128</option>
            <option value="ean_8">EAN-8</option>
            <option value="ean_13">EAN-13</option>
            <option value="itf">ITF</option>
            <option value="upc_a">UPC-A</option>
            <option value="upc_e">UPC-E</option>
          </select>
        </details>
      </section>
      <section className="form__scanner" ref={scannerRef}>
        <BarcodeScanner
          key={retryKey}
          onCapture={handleCapture}
          onError={handleError}
          options={{
            formats: selectedFormat ? [selectedFormat] : defaultFormats,
            delay: 100,
          }}
        />
        <div className="overlay">
          <div className="overlay-element top-left" />
          <div className="overlay-element top-right" />
          <div className="overlay-element bottom-left" />
          <div className="overlay-element bottom-right" />
        </div>
      </section>
      <section className="form__scanner__capture">
        <button
          type="button"
          className="pure-button pure-button-primary"
          onClick={captureAndAnalyze}
          disabled={isAnalyzing}
        >
          {isAnalyzing ? translated.analyzing : translated.captureButton}
        </button>
        {analyzeError && (
          <p className="form-error" role="alert">{analyzeError}</p>
        )}
      </section>
    </>
  )
}

const initScanner = () => {
  const container = document.getElementById('scanner')
  if (container) {
    const root = createRoot(container)
    // Override the locateFile function
    prepareZXingModule({
      overrides: {
        // @ts-ignore
        locateFile: (path, prefix) => {
          if (path.endsWith('.wasm')) {
            return container.dataset.zxing_wasm_url
          }
          return prefix + path
        },
      },
    })
    // @ts-ignore
    globalThis.BarcodeDetector ??= BarcodeDetector
    root.render(<Scanner />)
  }
}

document.addEventListener('DOMContentLoaded', initScanner, false)
