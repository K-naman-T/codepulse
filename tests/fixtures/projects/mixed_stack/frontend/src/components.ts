export class Component {
  constructor(private name: string) {}

  render(): string {
    return `<div>${this.name}</div>`;
  }
}
