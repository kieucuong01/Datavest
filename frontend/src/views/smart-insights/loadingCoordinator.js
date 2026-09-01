export async function runSectionLoaders (loaders = {}, setLoading = () => {}) {
  const entries = Object.entries(loaders)
  entries.forEach(([section]) => setLoading(section, true))

  const tasks = entries.map(async ([section, loader]) => {
    try {
      return { section, status: 'fulfilled', value: await loader() }
    } catch (reason) {
      return { section, status: 'rejected', reason }
    } finally {
      setLoading(section, false)
    }
  })

  return Promise.all(tasks)
}
