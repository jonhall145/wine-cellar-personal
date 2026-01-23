import React, { useState, useEffect, useRef, useCallback } from 'react'
import { createRoot } from 'react-dom/client'
import { BarcodeScanner, DetectedBarcode } from 'react-barcode-scanner'
// @ts-ignore
import django from 'django'

import { BarcodeDetector, prepareZXingModule } from 'barcode-detector/ponyfill'
import { CameraError, CameraErrorType } from './components/CameraError'
import { CameraLoader } from './components/CameraLoader'

const translated = {
  advanced: django.gettext('Advanced'),
  helptext: django.gettext(
    "Choose the type of barcode you want to scan, sometimes this can help if scanning doesn't work."
  ),
  captureButton: django.gettext('Force Scan'),
  analyzing: django.gettext('Analyzing...'),
  noBarcodeFound: django.gettext('No barcode found in image'),
  manualEntry: django.gettext('Enter Manually'),
  scannerTip: django.gettext('Hold steady and fill frame with barcode'),
}

/**
 * Preprocess an image for better barcode detection.
 * Creates multiple versions with different contrast/grayscale settings.
 */
const preprocessImage = (
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  ctx: CanvasRenderingContext2D
): string[] => {
  const images: string[] = []
  const width = video.videoWidth
  const height = video.videoHeight

  canvas.width = width
  canvas.height = height

  // 1. Original image
  ctx.drawImage(video, 0, 0)
  images.push(canvas.toDataURL('image/png'))

  // Get image data for processing
  const imageData = ctx.getImageData(0, 0, width, height)
  const data = imageData.data

  // 2. Grayscale + contrast enhanced
  const grayData = ctx.createImageData(width, height)
  let min = 255, max = 0

  // First pass: convert to grayscale and find min/max
  for (let i = 0; i < data.length; i += 4) {
    const gray = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
    grayData.data[i] = gray
    grayData.data[i + 1] = gray
    grayData.data[i + 2] = gray
    grayData.data[i + 3] = 255
    if (gray < min) min = gray
    if (gray > max) max = gray
  }

  // Second pass: contrast stretching and slight enhancement
  const range = max - min || 1
  const contrastFactor = 1.2
  for (let i = 0; i < grayData.data.length; i += 4) {
    // Normalize to 0-255
    let val = ((grayData.data[i] - min) / range) * 255
    // Increase contrast around midpoint
    val = ((val - 128) * contrastFactor) + 128
    val = Math.max(0, Math.min(255, val))
    grayData.data[i] = val
    grayData.data[i + 1] = val
    grayData.data[i + 2] = val
  }

  ctx.putImageData(grayData, 0, 0)
  images.push(canvas.toDataURL('image/png'))

  // 3. High contrast version (1.5x)
  const highContrastFactor = 1.5
  for (let i = 0; i < grayData.data.length; i += 4) {
    let val = grayData.data[i]
    val = ((val - 128) * highContrastFactor) + 128
    val = Math.max(0, Math.min(255, val))
    grayData.data[i] = val
    grayData.data[i + 1] = val
    grayData.data[i + 2] = val
  }

  ctx.putImageData(grayData, 0, 0)
  images.push(canvas.toDataURL('image/png'))

  return images
}

const Scanner = () => {
  const [selectedFormat, setSelectedFormat] = useState('any')
  const [cameraError, setCameraError] = useState<CameraErrorType>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)
  const [scanSuccess, setScanSuccess] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string>('')
  const scannerRef = useRef<HTMLDivElement>(null)
  const defaultFormats = ['ean_13', 'ean_8', 'upc_a', 'code_39', 'itf']

  useEffect(() => {
    // Check if we're on HTTPS or localhost
    const isSecureContext = window.isSecureContext
    if (!isSecureContext) {
      setCameraError('https')
      setIsInitializing(false)
    }
  }, [])

  // Monitor video element for camera ready state
  useEffect(() => {
    if (cameraError) return

    const checkVideoReady = () => {
      if (!scannerRef.current) return
      const video = scannerRef.current.querySelector('video')
      if (video && video.videoWidth > 0 && video.videoHeight > 0) {
        setIsInitializing(false)
        setStatusMessage(translated.scannerTip)
      }
    }

    const interval = setInterval(checkVideoReady, 100)
    // Timeout after 10 seconds
    const timeout = setTimeout(() => {
      if (isInitializing) {
        setIsInitializing(false)
      }
    }, 10000)

    return () => {
      clearInterval(interval)
      clearTimeout(timeout)
    }
  }, [cameraError, isInitializing, retryKey])

  const handleCapture = (barcodes: DetectedBarcode[]) => {
    if (barcodes.length > 0) {
      setScanSuccess(true)
      setStatusMessage(`Barcode found: ${barcodes[0].rawValue}`)
      // Haptic feedback on successful scan
      if ('vibrate' in navigator) {
        navigator.vibrate(200)
      }
      // Brief delay to show success animation
      setTimeout(() => {
        window.location.href = '/wine/scan/' + barcodes[0].rawValue
      }, 300)
    }
  }

  const handleError = (error: unknown) => {
    console.error('Camera error:', error)
    setIsInitializing(false)

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
    setIsInitializing(true)
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
    setStatusMessage(translated.analyzing)

    try {
      // Create a canvas and draw the current video frame
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        throw new Error('Could not get canvas context')
      }

      // Generate preprocessed image versions
      const images = preprocessImage(video, canvas, ctx)

      // Get CSRF token
      const csrfToken = document.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]')?.value
        || document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content
        || ''

      // Send multiple images to server for analysis
      const response = await fetch('/wine/scan-barcode/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ images }),
      })

      const result = await response.json()

      if (result.success && result.barcode) {
        // Barcode found - show success and redirect
        setScanSuccess(true)
        setStatusMessage(`Barcode found: ${result.barcode}`)
        // Haptic feedback on successful scan
        if ('vibrate' in navigator) {
          navigator.vibrate(200)
        }
        setTimeout(() => {
          window.location.href = '/wine/scan/' + result.barcode
        }, 300)
      } else {
        setAnalyzeError(translated.noBarcodeFound)
        setStatusMessage('')
      }
    } catch (error) {
      console.error('Error analyzing image:', error)
      setAnalyzeError(error instanceof Error ? error.message : 'Analysis failed')
      setStatusMessage('')
    } finally {
      setIsAnalyzing(false)
    }
  }, [])

  if (cameraError) {
    return <CameraError errorType={cameraError} onRetry={handleRetry} />
  }

  return (
    <div
      role="application"
      aria-label="Barcode Scanner"
      aria-describedby="scanner-status"
    >
      <section className="form__scanner__details">
        <details>
          <summary>{translated.advanced}</summary>
          <p className="form-hint">{translated.helptext}</p>
          <select
            value={selectedFormat}
            onChange={(e) => setSelectedFormat(e.target.value)}
            aria-label="Barcode format"
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
      <section
        className={`form__scanner ${scanSuccess ? 'form__scanner--success' : ''}`}
        ref={scannerRef}
      >
        {isInitializing && <CameraLoader />}
        <BarcodeScanner
          key={retryKey}
          onCapture={handleCapture}
          onError={handleError}
          options={{
            formats: selectedFormat ? [selectedFormat] : defaultFormats,
            delay: 200,  // Increased from 100 for better detection
          }}
        />
        <div className="overlay" aria-hidden="true">
          <div className="overlay-element top-left" />
          <div className="overlay-element top-right" />
          <div className="overlay-element bottom-left" />
          <div className="overlay-element bottom-right" />
          <div className="overlay__scan-line" />
        </div>
      </section>
      {/* Screen reader status announcer */}
      <div id="scanner-status" className="sr-only" aria-live="polite">
        {statusMessage}
      </div>
      {!isInitializing && statusMessage && !analyzeError && (
        <p className="scanner-tip" aria-hidden="true">
          <i className="fa-solid fa-lightbulb" aria-hidden="true"></i> {statusMessage}
        </p>
      )}
      <section className="form__scanner__capture" style={{ position: 'relative', zIndex: 10, paddingBottom: '2rem' }}>
        <button
          type="button"
          className={`pure-button pure-button-primary ${isAnalyzing ? 'button--loading' : ''}`}
          onClick={captureAndAnalyze}
          disabled={isAnalyzing || isInitializing}
          aria-busy={isAnalyzing}
          aria-describedby="capture-button-desc"
          style={{ marginBottom: '1rem', width: '100%', minHeight: '44px' }}
        >
          {isAnalyzing && <span className="spinner spinner--sm" aria-hidden="true" />}
          {isAnalyzing ? translated.analyzing : (translated.captureButton || 'Force Scan')}
        </button>
        <span id="capture-button-desc" className="sr-only">
          Captures current camera frame and analyzes it for barcodes
        </span>
        <a
          href="/wine/add/"
          className="pure-button button__secondary"
          style={{ width: '100%', minHeight: '44px', display: 'flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none' }}
        >
          {translated.manualEntry || 'Enter Manually'}
        </a>
        {analyzeError && (
          <p className="form-error" role="alert">{analyzeError}</p>
        )}
      </section>
    </div>
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
