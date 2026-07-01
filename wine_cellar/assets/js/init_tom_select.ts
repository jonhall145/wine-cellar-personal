import TomSelect from 'tom-select'
import { TomSettings } from 'tom-select/dist/esm/types/settings.js';
import { RecursivePartial, TomCreateCallback} from 'tom-select/dist/esm/types/core.js';


// Store TomSelect instances by element name for cross-field interaction
const tsInstances: Record<string, TomSelect> = {}

function normaliseTomSelectValue(value: string | string[] | null | undefined): string[] {
  if (Array.isArray(value)) {
    return value
  }
  if (typeof value === 'string' && value !== '') {
    return [value]
  }
  return []
}

function initTomSelect (): void {
  document.querySelectorAll('select:not([data-native-select="true"])').forEach((el) => {
    const rawConfig : string | undefined = el.dataset.tom_config
    const clear : boolean = Boolean(JSON.parse(el.dataset.clear ?? "false"))
    const clearOpts : boolean = Boolean(JSON.parse(el.dataset.clearOpts ?? "false"))
    const enableSearch : boolean = Boolean(JSON.parse(el.dataset.search ?? "false"))
    let config : RecursivePartial<TomSettings> = {
      create: false,
      closeAfterSelect: true,
      maxItems: 1,
      // disable search by default
      controlInput: '',
      allowEmptyOption: true,
    }
    if (rawConfig) {
      config = JSON.parse(rawConfig)
      if (config.create) {
        config.create = function (input:string,create:TomCreateCallback) : boolean  {
          create({value: 'tom_new_opt' + input, text: input })
          return true
        }
        // Enable search if create is true, so users can type
        delete config.controlInput
      }
    }
    // Enable search if data-search="true" is set
    if (enableSearch) {
      delete config.controlInput
    }
    const ts = new TomSelect(el, config)
    if (clear) {
      ts.clear()
    }
    if (clearOpts) {
      ts.clearOptions()
    }
    // Store instance by element name for later lookup
    if (el.name) {
      tsInstances[el.name] = ts
    }
  })

  // Set up country-based appellation filtering
  initAppellationCountryFilter()
  initWineTypeGrapeFilter()
}

function initAppellationCountryFilter(): void {
  const appellationSelect = document.querySelector('select[name="appellation"]') as HTMLSelectElement | null
  if (!appellationSelect) return

  const countryMapRaw = appellationSelect.dataset.appellationCountries
  if (!countryMapRaw) return

  const countryMap: Record<string, string> = JSON.parse(countryMapRaw)
  const appellationTs = tsInstances['appellation']
  const countryTs = tsInstances['country']
  if (!appellationTs || !countryTs) return

  // Store all original options so we can restore them when filtering
  const allOptions: Record<string, {value: string, text: string, country: string}> = {}
  for (const [value, data] of Object.entries(appellationTs.options)) {
    if (value === '') continue // skip empty option
    allOptions[value] = {
      value,
      text: (data as any).text || '',
      country: countryMap[value] || '',
    }
  }

  function filterByCountry(countryCode: string): void {
    const currentValue = appellationTs.getValue()

    // Clear and rebuild options
    appellationTs.clearOptions()
    // Re-add empty option
    appellationTs.addOption({value: '', text: '---------'})

    for (const opt of Object.values(allOptions)) {
      if (!countryCode || opt.country === countryCode) {
        appellationTs.addOption({value: opt.value, text: opt.text})
      }
    }

    // Keep current selection if it matches the country, otherwise clear
    if (currentValue && allOptions[currentValue]?.country === countryCode) {
      appellationTs.setValue(currentValue, true)
    } else if (countryCode) {
      appellationTs.clear(true)
    }

    appellationTs.refreshOptions(false)
  }

  // Listen for country changes
  countryTs.on('change', (value: string) => {
    filterByCountry(value)
  })

  // Apply initial filter if country is already set
  const initialCountry = countryTs.getValue() as string
  if (initialCountry) {
    filterByCountry(initialCountry)
  }
}

function initWineTypeGrapeFilter(): void {
  const grapeSelect = document.querySelector('select[name="grapes"][data-grape-wine-types]') as HTMLSelectElement | null
  const wineTypeSelect = document.querySelector('select[name="wine_type"]') as HTMLSelectElement | null
  if (!grapeSelect || !wineTypeSelect) return

  const grapeTypeMapRaw = grapeSelect.dataset.grapeWineTypes
  if (!grapeTypeMapRaw) return

  const grapeTs = tsInstances['grapes']
  const wineTypeTs = tsInstances['wine_type']
  if (!grapeTs || !wineTypeTs) return

  const grapeTypeMap: Record<string, string[]> = JSON.parse(grapeTypeMapRaw)
  const allOptions = Array.from(grapeSelect.options)
    .filter((option) => option.value !== '')
    .map((option) => ({
      value: option.value,
      text: option.text,
    }))

  function reorderGrapes(selectedWineTypes: string[]): void {
    const selectedGrapes = normaliseTomSelectValue(grapeTs.getValue() as string | string[] | null)
    const hasSelectedTypes = selectedWineTypes.length > 0

    const prioritisedOptions = allOptions.filter((option) => {
      const wineTypes = grapeTypeMap[option.value] ?? []
      if (hasSelectedTypes) {
        return wineTypes.some((wineType) => selectedWineTypes.includes(wineType))
      }
      return wineTypes.length > 0
    })
    const remainingOptions = allOptions.filter((option) => {
      const wineTypes = grapeTypeMap[option.value] ?? []
      if (hasSelectedTypes) {
        return !wineTypes.some((wineType) => selectedWineTypes.includes(wineType))
      }
      return wineTypes.length === 0
    })

    grapeTs.clear(true)
    grapeTs.clearOptions()
    grapeTs.addOptions([...prioritisedOptions, ...remainingOptions])
    if (selectedGrapes.length > 0) {
      grapeTs.setValue(selectedGrapes, true)
    }
    grapeTs.refreshOptions(false)
  }

  wineTypeTs.on('change', () => {
    reorderGrapes(normaliseTomSelectValue(wineTypeTs.getValue() as string | string[] | null))
  })

  reorderGrapes(normaliseTomSelectValue(wineTypeTs.getValue() as string | string[] | null))
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTomSelect)
} else {
  initTomSelect()
}
