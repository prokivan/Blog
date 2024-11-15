"""Added avatar

Revision ID: d1f18c1215fe
Revises: b4c998d05e97
Create Date: 2024-11-08 12:30:16.380940

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1f18c1215fe'
down_revision = 'b4c998d05e97'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.alter_column('timestamp',
               existing_type=sa.DATETIME(),
               nullable=False)
        batch_op.alter_column('read',
               existing_type=sa.BOOLEAN(),
               nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.alter_column('read',
               existing_type=sa.BOOLEAN(),
               nullable=True)
        batch_op.alter_column('timestamp',
               existing_type=sa.DATETIME(),
               nullable=True)

    # ### end Alembic commands ###
