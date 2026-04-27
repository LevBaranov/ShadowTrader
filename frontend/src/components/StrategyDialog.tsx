import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
} from "@mui/material";
import { useState } from "react";
import { buttonStyles } from "../theme/buttons";

type Props = {
  open: boolean;
  onClose: () => void;
  onSave: (strategy: { portfolio: string; index: string }) => void;
};

export default function StrategyDialog({ open, onClose, onSave }: Props) {
  const [portfolio, setPortfolio] = useState("");
  const [index, setIndex] = useState("");

  const handleSave = () => {
    onSave({ portfolio, index });
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth>
      <DialogTitle>Новая стратегия</DialogTitle>

      <DialogContent>
        <TextField
          fullWidth
          label="Портфель"
          value={portfolio}
          onChange={(e) => setPortfolio(e.target.value)}
          margin="normal"
        />

        <TextField
          fullWidth
          label="Индекс"
          value={index}
          onChange={(e) => setIndex(e.target.value)}
          margin="normal"
        />
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>

        <Button sx={buttonStyles} onClick={handleSave}>
          Сохранить
        </Button>
      </DialogActions>
    </Dialog>
  );
}