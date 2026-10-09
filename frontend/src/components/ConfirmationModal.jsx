import Button from "./Button";
import Modal from "./Modal";

export default function ConfirmationModal({
  open, title = "Confirmar acción", message, confirmLabel = "Confirmar", onConfirm, onCancel, loading, variant = "primary",
}) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={loading}>Cancelar</Button>
          <Button variant={variant} onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
        </>
      }
    >
      <p>{message}</p>
    </Modal>
  );
}
