import React from 'react'
// @ts-ignore
import django from 'django'

const translated = {
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
}

export type CameraErrorType = 'permission' | 'https' | 'notfound' | 'unknown' | null

// Get Font Awesome icon class for error type
const getErrorIcon = (errorType: CameraErrorType): string => {
  switch (errorType) {
    case 'permission':
      return 'fa-video-slash'
    case 'https':
      return 'fa-lock'
    case 'notfound':
      return 'fa-camera'
    default:
      return 'fa-triangle-exclamation'
  }
}

interface CameraErrorProps {
  errorType: CameraErrorType
  onRetry: () => void
}

export const CameraError: React.FC<CameraErrorProps> = ({ errorType, onRetry }) => {
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

  const iconClass = getErrorIcon(errorType)
  const isNotFound = errorType === 'notfound'

  return (
    <div className="camera-error" role="alert" aria-live="assertive">
      <div className={`camera-error__icon-container camera-error__icon-container--${errorType || 'unknown'}`}>
        <i className={`fa-solid ${iconClass}${isNotFound ? ' camera-error__icon--crossed' : ''}`} aria-hidden="true"></i>
      </div>
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

export default CameraError
