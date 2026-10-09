import { Component } from "react";

/** Evita pantallas en blanco ante errores inesperados de renderizado. */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Error de interfaz:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="fatal-error" role="alert">
          <h1>Algo salió mal</h1>
          <p>Ocurrió un error inesperado en la interfaz. Recargue la página para continuar.</p>
          <button type="button" className="btn btn-primary btn-md" onClick={() => window.location.reload()}>
            Recargar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
