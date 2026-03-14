// Compression settings
const MAX_DIMENSION = 2048 // Max width or height in pixels
const JPEG_QUALITY = 0.85 // 85% quality
const MAX_FILE_SIZE = 1024 * 1024 // 1MB - only compress if larger

/**
 * Compress an image file using Canvas API
 * Returns a Blob of the compressed JPEG image
 */
async function compressImage(file: File): Promise<Blob> {
  return new Promise((resolve, reject) => {
    // Skip compression for small files
    if (file.size <= MAX_FILE_SIZE) {
      resolve(file)
      return
    }

    const img = new Image()
    img.onload = () => {
      // Calculate new dimensions maintaining aspect ratio
      let { width, height } = img
      if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
        if (width > height) {
          height = Math.round((height * MAX_DIMENSION) / width)
          width = MAX_DIMENSION
        } else {
          width = Math.round((width * MAX_DIMENSION) / height)
          height = MAX_DIMENSION
        }
      }

      // Create canvas and draw resized image
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        reject(new Error('Could not get canvas context'))
        return
      }

      // Use high-quality image smoothing
      ctx.imageSmoothingEnabled = true
      ctx.imageSmoothingQuality = 'high'
      ctx.drawImage(img, 0, 0, width, height)

      // Convert to JPEG blob
      canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve(blob)
          } else {
            reject(new Error('Failed to compress image'))
          }
        },
        'image/jpeg',
        JPEG_QUALITY
      )
    }

    img.onerror = () => reject(new Error('Failed to load image'))

    // Load image from file
    const reader = new FileReader()
    reader.onload = (e) => {
      img.src = e.target?.result as string
    }
    reader.onerror = () => reject(new Error('Failed to read file'))
    reader.readAsDataURL(file)
  })
}

/**
 * Create a new File object from a Blob with the same name
 */
function blobToFile(blob: Blob, originalFile: File): File {
  // Generate new filename with .jpg extension
  const originalName = originalFile.name
  const baseName = originalName.replace(/\.[^/.]+$/, '')
  const newName = `${baseName}.jpg`

  return new File([blob], newName, {
    type: 'image/jpeg',
    lastModified: Date.now(),
  })
}

/**
 * Replace the file in an input element with a new file
 * Uses DataTransfer API to update the FileList
 */
function replaceInputFile(input: HTMLInputElement, newFile: File): void {
  const dataTransfer = new DataTransfer()
  dataTransfer.items.add(newFile)
  input.files = dataTransfer.files
}

function initImagePreview() {
  document.querySelectorAll('input[type="file"]').forEach((inputEl) => {
    const input = inputEl as HTMLInputElement
    const preview = input
      .closest('.form-container')
      ?.querySelector('.image-preview') as HTMLImageElement | null
    const hasInitial = preview?.src !== ''
    const wrapper = preview?.parentElement
    const clearCheckbox = input
      .closest('.form-container')
      ?.querySelector('.image-clear-checkbox') as HTMLInputElement | null

    input.addEventListener('change', async () => {
      const file = input.files?.[0]
      if (!file || !file.type.startsWith('image/')) {
        if (wrapper && !wrapper.className.includes('hidden')) {
          wrapper.classList.add('hidden')
        }
        return
      }

      try {
        // Compress the image
        const compressedBlob = await compressImage(file)
        const compressedFile = blobToFile(compressedBlob, file)

        // Replace the file in the input with the compressed version
        replaceInputFile(input, compressedFile)

        // Show preview of compressed image
        const reader = new FileReader()
        reader.onload = () => {
          if (preview && reader.result) {
            if (wrapper && wrapper.className.includes('hidden')) {
              wrapper.classList.remove('hidden')
            }
            preview.src = reader.result as string
            if (clearCheckbox && clearCheckbox.checked) {
              clearCheckbox.checked = false
            }
          }
        }
        reader.readAsDataURL(compressedFile)
      } catch (error) {
        console.error('Image compression failed:', error)
        // Fall back to showing original image
        const reader = new FileReader()
        reader.onload = () => {
          if (preview && reader.result) {
            if (wrapper && wrapper.className.includes('hidden')) {
              wrapper.classList.remove('hidden')
            }
            preview.src = reader.result as string
            if (clearCheckbox && clearCheckbox.checked) {
              clearCheckbox.checked = false
            }
          }
        }
        reader.readAsDataURL(file)
      }
    })

    if (clearCheckbox && preview) {
      const setClearControlLabels = (checked: boolean) => {
        const clearTitle = 'Clear Image'
        const restoreTitle = 'Restore image'
        const title = checked ? restoreTitle : clearTitle
        clearCheckbox.title = title
        clearCheckbox.setAttribute('aria-label', title)
        clearCheckbox.setAttribute('aria-pressed', checked ? 'true' : 'false')
      }

      setClearControlLabels(!!clearCheckbox.checked)

      clearCheckbox.addEventListener('change', () => {
        if (clearCheckbox.checked) {
          preview.dataset.originalSrc = preview.src || ''
          preview.src = ''
          if (!hasInitial) {
            if (wrapper && !wrapper.className.includes('hidden')) {
              wrapper.classList.add('hidden')
            }
          }
        } else {
          if (preview.dataset.originalSrc) {
            preview.src = preview.dataset.originalSrc
            delete preview.dataset.originalSrc
          }
        }
        setClearControlLabels(!!clearCheckbox.checked)
      })
      if (clearCheckbox.checked && hasInitial) {
        clearCheckbox.dispatchEvent(new Event('change', { bubbles: true }))
      }
    }
  })
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initImagePreview)
} else {
  initImagePreview()
}
