interface Props {
  text: string
}

export default function Message({ text }: Props) {
  return <div>{text}</div>
}
