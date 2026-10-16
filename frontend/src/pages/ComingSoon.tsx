import styles from './ComingSoon.module.css'

export function ComingSoon({ title, phase }: { title: string; phase: string }) {
  return (
    <section className={styles.box} aria-labelledby="cs-title">
      <h1 id="cs-title" className={styles.title}>
        {title}
      </h1>
      <p className={styles.text}>此頁將於 {phase} 完成。目前為新網站地基（P0）。</p>
    </section>
  )
}
