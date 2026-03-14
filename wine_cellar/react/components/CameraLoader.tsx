import React from 'react'
const translated = {
  initializingCamera: 'Initializing camera...',
}

interface CameraLoaderProps {
  message?: string
}

export const CameraLoader: React.FC<CameraLoaderProps> = ({ message }) => (
  <div className="camera-loader" role="status" aria-live="polite">
    <div className="camera-loader__icon-container">
      <i className="fa-solid fa-camera" aria-hidden="true"></i>
    </div>
    <div className="camera-loader__spinner" aria-hidden="true"></div>
    <p className="camera-loader__text">{message || translated.initializingCamera}</p>
  </div>
)

export default CameraLoader
