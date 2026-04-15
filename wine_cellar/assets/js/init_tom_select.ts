import TomSelect from 'tom-select'
import { TomSettings } from 'tom-select/dist/esm/types/settings.js';
import { RecursivePartial, TomCreateCallback} from 'tom-select/dist/esm/types/core.js';


// Store TomSelect instances by element ID for cross-field interaction
const tsInstances: Record<string, TomSelect> = {}

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

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTomSelect)
} else {
  initTomSelect()
}
